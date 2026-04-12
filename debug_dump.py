import json

with open('ocr_full_dump.json', 'r') as f:
    data = json.load(f)

for fname in ['InterCiti_T4_2025.pdf', 'RBC_T4.pdf', 'Sunlife_T3.pdf', 'Sunlife_T4PS.pdf', 'CSI_T2202.pdf']:
    print(f"\n{'='*60}")
    print(f"  {fname}")
    print(f"{'='*60}")
    for b in data[fname]:
        bbox = b['raw_bbox']
        cx = int((bbox[0][0] + bbox[2][0]) / 2)
        cy = int((bbox[0][1] + bbox[2][1]) / 2)
        text = b['text']
        print(f"  cy={cy:5d}  cx={cx:5d}  |  {text}")
