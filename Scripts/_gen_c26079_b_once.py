# -*- coding: utf-8 -*-
from __future__ import annotations
import importlib.util
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'Scripts'))
spec = importlib.util.spec_from_file_location('g9', ROOT / 'Scripts' / '09_generate_freight_customs_drafts.py')
g9 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(g9)

IUTE_ADDR = 'IUTE - AWD 3PL - 16155 W Elwood St - GOODYEAR, AZ 85338 - United States'
PROTOCOL = '20260731806'

def _now():
    return datetime.now(timezone.utc).astimezone().strftime('%Y-%m-%dT%H:%M:%S%z')

def _err_pct(b, a):
    if a == 0:
        return 0.0 if b == 0 else None
    return abs(b - a) / a * 100.0

def gate(er):
    if er is None:
        return 'CONFIRM'
    return 'PASS' if er <= 1.0 else 'CONFIRM'

def main():
    project = next((ROOT / '1_Input_Raw' / 'Shipments').glob('*C26079*'))
    rec = json.loads((ROOT / '2_Processed_AI/drafts/C26079-B_awd_recognize.json').read_text(encoding='utf-8'))
    wh_rec = rec['warehouses'][0]
    specs = [{'fnsku': s['fnsku'], 'qty_cartons': int(s['qty_cartons'])} for s in wh_rec['specs']]
    master = g9.load_master_by_fnsku()
    missing = [s for s in specs if s['fnsku'] not in master]
    if missing:
        print('STOP: master join missing FNSKU:', missing, file=sys.stderr)
        return 2
    g9.WH_ADDRESS['IUTE'] = {'freight_addr': IUTE_ADDR}
    row = {
        'warehouse_code': 'IUTE',
        'fba_shipment_id': wh_rec['fba_shipment_id'],
        'tracking_id': wh_rec.get('tracking_id') or '',
        'cartons': int(wh_rec['qty_cartons']),
        'strips': int(wh_rec['qty_strips']),
        'store': 'C04',
    }
    money = g9.warehouse_money_weights(specs, master)
    raw = float(money['declare_amount_raw'])
    unit, amount = g9.price_check(raw, row['strips'])
    freight_dir = project / '\u8d27\u4ee3\u5165\u5e93\u8d34\u4e0b\u5355\u8868'
    customs_dir = project / '\u62a5\u5173\u8d44\u6599\u8868'
    reconcile_dir = project / '\u62c6\u5355\u6bd4\u5bf9'
    for d in (freight_dir, customs_dir, reconcile_dir):
        d.mkdir(parents=True, exist_ok=True)
    freight_name = '\u8d27\u4ee3\u4e0b\u5355\u8868_C26079-B 2026.7.31\u684c\u5e03 AWD-IUTE 140\u7bb1.xlsx'
    customs_name = '\u7545\u9009+\u6ce2\u4e3d\u4e1d 2026.7.31\u53d1\u8d27 C26079-B AWD-IUTE 140\u7bb1 \u5e02\u573a\u91c7\u8d2d\u6570\u636e.xlsx'
    freight_path = freight_dir / freight_name
    customs_path = customs_dir / customs_name
    if not g9.FREIGHT_TEMPLATE.is_file() or not g9.CUSTOMS_TEMPLATE.is_file():
        print('missing templates', file=sys.stderr)
        return 1
    shutil.copy2(g9.FREIGHT_TEMPLATE, freight_path)
    shutil.copy2(g9.CUSTOMS_TEMPLATE, customs_path)
    g9.fill_freight(freight_path, row, money, unit)
    # openpyxl save strips WPS cellimages; fill_freight reinjects — belt-and-suspenders for B-leg
    g9._reinject_freight_media(freight_path, g9.FREIGHT_TEMPLATE)
    import zipfile as _zipfile
    with _zipfile.ZipFile(freight_path, 'r') as _zf:
        _mc = len([n for n in _zf.namelist() if n.startswith('xl/media/') and not n.endswith('/')])
    print('freight xl/media count after reinject:', _mc)
    g9.fill_customs(customs_path, row, money, unit, amount, PROTOCOL)
    a_amt, a_net, a_gross = raw, float(money['net_kg']), float(money['gross_kg'])
    b_amt, b_net, b_gross = amount, a_net, a_gross
    er_amt, er_net, er_gross = _err_pct(b_amt, a_amt), _err_pct(b_net, a_net), _err_pct(b_gross, a_gross)
    gate_result = {'declare': gate(er_amt), 'net': gate(er_net), 'gross': gate(er_gross)}
    gate_result['overall'] = 'PASS' if all(gate_result[k] == 'PASS' for k in ('declare', 'net', 'gross')) else 'CONFIRM'
    summary = {
        'generated_at': _now(),
        'order_code': rec.get('order_code', 'EF-C26079-C04-36460'),
        'split_leg_id': 'C26079-B',
        'channel': 'AWD',
        'warehouse_code': 'IUTE',
        'pricing_method': 'per_warehouse: raw=sum(cartons*master_1039_ctn_price); unit=round(raw/strips,2); amount=round(unit*strips,2)',
        'note': 'draft B AWD IUTE 140ctn 4200 strips',
        'files': [{
            'warehouse_code': 'IUTE', 'channel': 'AWD', 'fba_shipment_id': row['fba_shipment_id'],
            'tracking_id': row['tracking_id'], 'po_id': wh_rec.get('po_id'),
            'cartons': row['cartons'], 'strips': row['strips'],
            'raw_carton_x_price': round(raw, 2), 'unit_price_usd': unit, 'declare_amount_usd': amount,
            'net_kg': money['net_kg'], 'gross_kg': money['gross_kg'], 'protocol_no': PROTOCOL,
            'freight_file': str(freight_path), 'customs_file': str(customs_path), 'specs': specs,
        }],
        'reconcile': {
            'doc': 'Templates/Amount_Weight_Reconcile.md',
            'A_spec': {'amount': round(a_amt, 2), 'net_kg': round(a_net, 2), 'gross_kg': round(a_gross, 2)},
            'B_warehouse': {'amount': round(b_amt, 2), 'net_kg': round(b_net, 2), 'gross_kg': round(b_gross, 2)},
            'error_rate_pct': {
                'declare': None if er_amt is None else round(er_amt, 4),
                'net': None if er_net is None else round(er_net, 4),
                'gross': None if er_gross is None else round(er_gross, 4),
            },
            'pass_max_pct': 1.0, 'gate': gate_result,
        },
        'warnings': [],
    }
    if gate_result['overall'] != 'PASS':
        summary['warnings'].append('error rate >1pct confirm required')
    drafts = ROOT / '2_Processed_AI' / 'drafts'
    drafts.mkdir(parents=True, exist_ok=True)
    summary_path = drafts / 'C26079-B_freight_customs_summary.json'
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
    today = datetime.now(timezone.utc).astimezone().strftime('%Y-%m-%d')
    reconcile_json = {
        'ticket': 'C26079-B', 'channel': 'AWD', 'warehouse': 'IUTE', 'confirmed_at': today,
        'spec_aggregate': {'amount': round(a_amt, 2), 'net_kg': round(a_net, 2), 'gross_kg': round(a_gross, 2), 'cartons': row['cartons'], 'strips': row['strips']},
        'warehouse_declare_after_price_check': {'amount': round(b_amt, 2), 'unit_usd': unit},
        'error_rates': {'declare_pct': None if er_amt is None else round(er_amt, 4), 'net_pct': None if er_net is None else round(er_net, 4), 'gross_pct': None if er_gross is None else round(er_gross, 4)},
        'gate_result': gate_result, 'specs': specs,
    }
    reconcile_json_path = drafts / 'C26079-B_amount_weight_reconcile.json'
    reconcile_json_path.write_text(json.dumps(reconcile_json, ensure_ascii=False, indent=2), encoding='utf-8')
    delta_amt = round(b_amt - a_amt, 2)
    reconcile_md_path = reconcile_dir / 'C26079-B_amount_weight_reconcile.md'
    md = ['# C26079-B amount/weight reconcile (AWD IUTE)', '', 'unit=' + str(unit), 'amount=' + str(amount), 'net=' + str(money['net_kg']), 'gross=' + str(money['gross_kg'])]
    reconcile_md_path.write_text(chr(10).join(md), encoding='utf-8')
    print('unit={} amount={} net={} gross={}'.format(unit, amount, money['net_kg'], money['gross_kg']))
    erd=summary['reconcile']['error_rate_pct']['declare']
    ern=summary['reconcile']['error_rate_pct']['net']
    erg=summary['reconcile']['error_rate_pct']['gross']
    print('error_rate declare={}% net={}% gross={}% gate={}'.format(erd, ern, erg, gate_result['overall']))
    print('wrote', freight_path)
    print('wrote', customs_path)
    print('wrote', summary_path)
    print('wrote', reconcile_md_path)
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
