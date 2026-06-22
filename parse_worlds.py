#!/usr/bin/env python3
"""RSDW World Save Parser — standalone, paths relative to this file."""
import re, struct, json, os, math, bisect
from collections import defaultdict

BASE     = os.path.dirname(os.path.abspath(__file__))
CHEST_HTML   = os.path.join(BASE, 'RSDW_Chest_Map.html')
SAVE_DIR     = os.path.join(BASE, 'Saved', 'SaveGames')
OUT_DIR      = BASE
GUID_MAP_PATH= os.path.join(BASE, 'guid_map.json')
MASTER_PATH  = os.path.join(BASE, 'Master_Checklist_RSDW_v2.xlsx')

WORLDS = {
    'Cotswolds':       'Cotswolds.sav',
    'Season1LetsPlay': 'Season1LetsPlay.sav',
    'BuffTheBuilder':  'Buff the Builder.sav',
}

STORAGE_CLASSES = {
    'BP_BaseBuilding_Chest_Iron_C':      ('Iron Chest',       'chest',     'IRON'),
    'BP_BaseBuilding_Chest_C':           ('Oak Chest',        'chest',     'OAK'),
    'BP_BaseBuilding_Chest_Small_C':     ('Ash Chest',        'chest',     'ASH'),
    'BP_BaseBuilding_PersonalChest_C':   ('Personal Chest',   'chest',     'PERS'),
    'BP_BaseBuilding_Crate_C':           ('Crate',            'chest',     'CRAT'),
    'BP_BaseBuilding_WeaponRack_C':      ('Weapon Rack',      'rack',      'WRCK'),
    'BP_BaseBuilding_ArmourMannequin_C': ('Armour Mannequin', 'rack',      'MANEN'),
    'BP_BaseBuilding_CapeRack_C':        ('Cape Rack',        'rack',      'CAPE'),
    'BP_BaseBuilding_CapeHook_C':        ('Cape Hook',        'rack',      'CHOK'),
    'BP_BaseBuilding_LumberStorage_C':   ('Lumber Storage',   'chest',     'LUMB'),
    'BP_BaseBuilding_FishingBarrel_C':   ('Fishing Barrel',   'chest',     'FISH'),
    'BP_BaseBuilding_TackleBox_C':       ('Tackle Box',       'chest',     'TACK'),
    'BP_BaseBuilding_Lodestone_C':       ('Lodestone',        'lodestone', 'LODE'),
}

RACK_TYPES = {'Weapon Rack', 'Armour Mannequin', 'Cape Rack', 'Cape Hook'}

MANUAL_NAMES = {
    'OJSTGEEYP4OZy5dkiMIrCQ': 'Bronze Platebody',
    'fLnzAkbRfk6nK_w2hn8Wbg': 'Bronze Platelegs',
    '2vSF4Se4lGiOYMbYAZqRoA': 'Fang Arrows',
    'Pc6vpkbmfa3yXnaREyZM2g':  'Tome of the Titan',
}

GUID_RE = re.compile(r'^[A-Za-z0-9_\-]{22}$')

# ── Name table ────────────────────────────────────────────────
def build_name_table():
    names = {}
    # From old chest map HTML
    try:
        html = open(CHEST_HTML, 'r', errors='replace').read()
        for m in re.finditer(r'"item_id":\s*"([^"]+)",\s*"name":\s*"([^"]+)"', html):
            names[m.group(1)] = m.group(2)
    except: pass
    # From guid_map.json
    try:
        gm = json.load(open(GUID_MAP_PATH))
        for pid, v in gm['by_persistence_id'].items():
            nm = v.get('name') or v.get('internal_name')
            if nm and pid not in names:
                names[pid] = nm
    except: pass
    # Manual overrides
    names.update(MANUAL_NAMES)
    return names

NAME_TABLE = build_name_table()

# From Master Checklist (loaded once)
MASTER = {}
try:
    import pandas as pd
    df = pd.read_excel(MASTER_PATH, sheet_name='Item ID Directory', header=None)
    MASTER = {str(r[0]).strip(): str(r[1]).strip()
              for _, r in df.iloc[3:].iterrows()
              if pd.notna(r[0]) and pd.notna(r[1])}
except Exception as e:
    print(f"  [warn] Master Checklist not loaded: {e}")

print(f"Name table: {len(NAME_TABLE)} entries, Master Checklist: {len(MASTER)} entries")

def resolve_guid(g):
    return NAME_TABLE.get(g, g)

# ── Binary helpers ────────────────────────────────────────────
def parse_class_table(data):
    lode_bytes = b'BP_BaseBuilding_Lodestone_C'
    anchor = data[:12000].find(lode_bytes)
    if anchor == -1: return {}
    lode_pos = None
    for t in range(max(0, anchor-300), anchor+1):
        slen = struct.unpack_from('<I', data, t)[0]
        if 20 <= slen <= 300:
            s = data[t+4:t+4+slen-1].decode('utf-8', 'replace')
            if lode_bytes.decode() in s and '\x00' not in s:
                lode_pos = t; break
    if lode_pos is None: return {}
    ts = lode_pos
    for _ in range(500):
        found = False
        for tl in range(5, 500):
            ps = ts - 4 - tl
            if ps < 0: break
            if struct.unpack_from('<I', data, ps)[0] == tl:
                s = data[ps+4:ps+4+tl-1].decode('utf-8', 'replace')
                if '\x00' not in s and len(s) >= 3 and s[0] in '/ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz_':
                    ts = ps; found = True; break
        if not found: break
    cls_map = {}
    p, i = ts, 0
    while p < min(len(data)-8, 25000):
        slen = struct.unpack_from('<I', data, p)[0]
        if slen == 0 or slen > 1024: break
        s = data[p+4:p+4+slen-1].decode('utf-8', 'replace')
        if '\x00' in s: break
        cn = s.split('.')[-1]
        cls_map[i] = cn; cls_map[cn] = i
        i += 1; p += 4 + slen
    print(f"  Class table: {i} entries")
    return cls_map

def parse_save(sav_path, world_name, html_objects=None):
    print(f"\n{'='*60}\nParsing: {world_name} ({os.path.getsize(sav_path)//1024} KB)")
    data = open(sav_path, 'rb').read()
    txt  = data.decode('latin-1')

    cls_map = parse_class_table(data)
    storage_idx = {}
    for cn, (dt, cat, pfx) in STORAGE_CLASSES.items():
        if cn in cls_map:
            storage_idx[cls_map[cn]] = (cn, dt, cat, pfx)
    print(f"  Mapped {len(storage_idx)} storage class types")

    # Extract storage SPWNs
    spwns = []
    p = 0
    while True:
        idx = data.find(b'SPWN', p)
        if idx == -1: break
        p = idx + 1
        if idx+60 > len(data): break
        sz  = struct.unpack_from('<I', data, idx+4)[0]
        cls = struct.unpack_from('<I', data, idx+8)[0]
        if sz < 100: continue
        if cls not in storage_idx: continue
        try:
            x = struct.unpack_from('<d', data, idx+28)[0]
            y = struct.unpack_from('<d', data, idx+36)[0]
        except: continue
        if not (-150000 < x < 450000 and -300000 < y < 450000): continue
        cn, dt, cat, pfx = storage_idx[cls]
        spwns.append({'pos': idx, 'cls': cls, 'type': dt, 'cat': cat,
                      'pfx': pfx, 'gx': round(x), 'gy': round(y)})
    print(f"  Storage SPWNs: {len(spwns)}")

    # Extract ItemData blobs
    blobs = []
    for m in re.finditer(r'\{[^{}]{5,300}\}', txt):
        blob = m.group()
        if '"ItemData"' not in blob: continue
        gm = re.search(r'"ItemData":\s*"([A-Za-z0-9_\-]{22})"', blob)
        if not gm: continue
        ig = re.search(r'"GUID":\s*"([A-Za-z0-9_\-]{22})"', blob)
        cm = re.search(r'"Count":\s*(\d+)', blob)
        dm = re.search(r'"Durability":\s*([\d.]+)', blob)
        item = {'pos': m.start(), 'g': gm.group(1),
                'ig': ig.group(1) if ig else None}
        if cm:   item['c'] = int(cm.group(1))
        elif dm: item['d'] = float(dm.group(1))
        else:    item['c'] = 1
        blobs.append(item)
    print(f"  ItemData blobs: {len(blobs)}")

    # Assign blobs to nearest preceding non-lodestone SPWN
    spwn_positions = [s['pos'] for s in spwns]
    MAX_DIST = 200000
    spwn_items = defaultdict(list)
    for blob in blobs:
        bp  = blob['pos']
        idx = bisect.bisect_right(spwn_positions, bp) - 1
        best_spwn = None
        for si in range(idx, -1, -1):
            s = spwns[si]
            if bp - s['pos'] > MAX_DIST: break
            if s['cat'] == 'lodestone': continue
            best_spwn = s; break
        if best_spwn:
            spwn_items[best_spwn['pos']].append(blob)

    # Build items per SPWN
    for spwn in spwns:
        spwn['name'] = ''; spwn['named'] = 0
        if spwn['cat'] == 'lodestone':
            spwn['items'] = []; continue
        blobs_for_spwn = spwn_items.get(spwn['pos'], [])
        item_totals = defaultdict(int)
        item_durs   = {}
        seen_inst   = set()
        for blob in blobs_for_spwn:
            ig = blob.get('ig')
            if ig:
                if ig in seen_inst: continue
                seen_inst.add(ig)
            g    = blob['g']
            name = resolve_guid(g)
            if 'c' in blob:
                item_totals[name] += blob['c']
            elif 'd' in blob:
                item_durs[name] = blob['d']
                item_totals[name] = max(item_totals[name], 1)
        items = []
        for name, total in sorted(item_totals.items()):
            e = {'name': name, 'count': total}
            if name in item_durs: e['durability'] = item_durs[name]
            items.append(e)
        spwn['items'] = items

    # Match with previous HTML objects (stable IDs)
    if html_objects:
        hbo = defaultdict(list)
        for o in html_objects: hbo[o['type']].append(o)
        for spwn in spwns:
            if spwn['cat'] == 'lodestone': continue
            best = None; bd = 2500
            for ho in hbo.get(spwn['type'], []):
                d = math.hypot(ho['gx']-spwn['gx'], ho['gy']-spwn['gy'])
                if d < bd: bd = d; best = ho
            if best:
                spwn['id'] = best['id']
                if not spwn['items'] and best.get('items'):
                    spwn['items'] = best['items']

    # Fresh IDs for unmatched
    used = set(s.get('id', '') for s in spwns if 'id' in s)
    ctr  = defaultdict(int)
    for s in spwns:
        if 'id' not in s:
            pfx = s['pfx']; ctr[pfx] += 1
            cid = f"{pfx}-{ctr[pfx]:03d}"
            while cid in used: ctr[pfx] += 1; cid = f"{pfx}-{ctr[pfx]:03d}"
            s['id'] = cid; used.add(cid)

    objects = [{'id': s['id'], 'type': s['type'], 'category': s['cat'],
                'name': s.get('name', ''), 'named': s.get('named', 0),
                'gx': s['gx'], 'gy': s['gy'],
                'n_items': len(s['items']), 'items': s['items']}
               for s in spwns]

    from collections import Counter as Ctr
    print(f"  Final: {len(objects)} objects")
    for t, cnt in Ctr(o['type'] for o in objects).most_common():
        ni = sum(1 for o in objects if o['type'] == t and o['n_items'] > 0)
        print(f"    {cnt:3d}x{t:<30s} {ni} with items")
    return objects

# ── Post-processing ───────────────────────────────────────────
def post_process(world, data):
    for o in data:
        # Racks/mannequins: keep only durability items
        if o['type'] in RACK_TYPES:
            o['items'] = [it for it in o['items'] if 'durability' in it]
        # Resolve any remaining GUIDs via Master Checklist
        for it in o['items']:
            nm = it['name']
            if nm in MANUAL_NAMES:
                it['name'] = MANUAL_NAMES[nm]
            elif GUID_RE.match(nm) and nm in MASTER:
                it['name'] = MASTER[nm]
        o['n_items'] = len(o['items'])
    # Add missing Temple Woods lodestone (Cotswolds only)
    if world == 'Cotswolds':
        if not any(o['category'] == 'lodestone'
                   and abs(o['gx']-30565) < 500
                   and abs(o['gy']-176395) < 500
                   for o in data):
            data.append({'id': 'LODE-MANUAL-001', 'type': 'Lodestone',
                         'category': 'lodestone', 'gx': 30565, 'gy': 176395,
                         'zone': 'Temple Woods', 'label': 'Temple Woods',
                         'items': [], 'n_items': 0})
    return data

# ── Main ──────────────────────────────────────────────────────
if __name__ == '__main__':
    html = []
    try:
        h = open(CHEST_HTML, 'r', errors='replace').read()
        m = re.search(r'const OBJECTS=(\[.*?\]);', h, re.DOTALL)
        if m: html = json.loads(m.group(1))
        print(f"Loaded {len(html)} HTML objects")
    except: pass

    for world_name, sav_file in WORLDS.items():
        sav_path = os.path.join(SAVE_DIR, sav_file)
        if not os.path.exists(sav_path):
            print(f"Skipping {world_name}: {sav_path} not found")
            continue
        objects = parse_save(sav_path, world_name, html)
        objects = post_process(world_name, objects)
        out_path = os.path.join(OUT_DIR, f'world_{world_name}.json')
        json.dump(objects, open(out_path, 'w'), indent=2)
        print(f"Written {len(objects)} objects → {out_path}")

    print("\nDone.")
