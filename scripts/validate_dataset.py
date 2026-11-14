import csv, json, re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'data' / 'novamart'

EXPECTED_TABLES = {
    'customers': ('customer_id', 10000),
    'sellers': ('seller_id', 500),
    'products': ('product_id', 2000),
    'marketing_campaigns': ('campaign_id', 50),
    'leads': ('lead_id', 15000),
    'marketing_events': ('event_id', 50000),
    'orders': ('order_id', 50000),
    'order_items': ('order_item_id', 125202),
    'payments': ('payment_id', 50000),
    'shipments': ('shipment_id', 50000),
    'returns': ('return_id', 3585),
    'support_tickets': ('ticket_id', 9970),
}

FKS = [
    ('products','seller_id','sellers','seller_id'),
    ('leads','campaign_id','marketing_campaigns','campaign_id'),
    ('leads','seller_id','sellers','seller_id'),
    ('leads','customer_id','customers','customer_id'),
    ('marketing_events','campaign_id','marketing_campaigns','campaign_id'),
    ('marketing_events','customer_id','customers','customer_id'),
    ('orders','customer_id','customers','customer_id'),
    ('order_items','order_id','orders','order_id'),
    ('order_items','product_id','products','product_id'),
    ('order_items','seller_id','sellers','seller_id'),
    ('payments','order_id','orders','order_id'),
    ('shipments','order_id','orders','order_id'),
    ('returns','order_id','orders','order_id'),
    ('returns','order_item_id','order_items','order_item_id'),
    ('support_tickets','customer_id','customers','customer_id'),
    ('support_tickets','order_id','orders','order_id'),
    ('support_tickets','product_id','products','product_id'),
]

def read_csv(path):
    with path.open(newline='', encoding='utf-8-sig') as f:
        return list(csv.DictReader(f))

def fail(msg):
    print(f'[FAIL] {msg}')
    return 1

def main():
    errors=[]
    tables={}
    for table,(pk,expected) in EXPECTED_TABLES.items():
        path=BASE/'structured'/f'{table}.csv'
        if not path.exists():
            errors.append(f'missing table: {path}')
            continue
        rows=read_csv(path); tables[table]=rows
        if len(rows)!=expected: errors.append(f'{table}: expected {expected} rows, found {len(rows)}')
        vals=[r.get(pk) for r in rows]
        if any(v in ('',None) for v in vals): errors.append(f'{table}.{pk}: blank primary key')
        if len(vals)!=len(set(vals)): errors.append(f'{table}.{pk}: duplicate primary key')
    for a,col,b,bcol in FKS:
        if a not in tables or b not in tables: continue
        valid={r[bcol] for r in tables[b]}
        bad=sum(1 for r in tables[a] if r.get(col) and r[col] not in valid)
        if bad: errors.append(f'{a}.{col} -> {b}.{bcol}: {bad} invalid references')

    # Source-of-truth row counts
    for table,(pk,expected) in EXPECTED_TABLES.items():
        path=BASE/'source_of_truth'/f'{table}.json'
        if not path.exists(): errors.append(f'missing source-of-truth: {path}'); continue
        data=json.loads(path.read_text(encoding='utf-8'))
        if len(data)!=expected: errors.append(f'SOT {table}: expected {expected}, found {len(data)}')

    meta=read_csv(BASE/'metadata/document_metadata.csv')
    links=read_csv(BASE/'metadata/document_entity_links.csv')
    docs=[p for p in (BASE/'documents').rglob('*') if p.is_file()]
    doc_rel={str(p.relative_to(BASE)).replace('\\','/') for p in docs}
    meta_rel={r['source_filename'] for r in meta}
    if doc_rel != meta_rel:
        errors.append(f'document/metadata file mismatch: missing metadata={sorted(doc_rel-meta_rel)}, extra metadata={sorted(meta_rel-doc_rel)}')
    doc_ids=[r['document_id'] for r in meta]
    if len(doc_ids)!=len(set(doc_ids)): errors.append('duplicate document_id in metadata')
    id_by_file={r['source_filename']:r['document_id'] for r in meta}
    if any(not r['document_id'] for r in meta): errors.append('blank document_id in metadata')
    for r in links:
        if r['source_filename'] not in id_by_file: errors.append(f'entity link references unknown file: {r["source_filename"]}')
        elif r['document_id'] != id_by_file[r['source_filename']]: errors.append(f'entity link ID mismatch for {r["source_filename"]}')
    valid_entities={
        'campaign': {r['campaign_id'] for r in tables['marketing_campaigns']},
        'product': {r['product_id'] for r in tables['products']},
        'customer': {r['customer_id'] for r in tables['customers']},
        'seller': {r['seller_id'] for r in tables['sellers']},
        'order': {r['order_id'] for r in tables['orders']},
        'order_item': {r['order_item_id'] for r in tables['order_items']},
    }
    for r in links:
        if r['entity_type'] in valid_entities and r['entity_id'] not in valid_entities[r['entity_type']]:
            errors.append(f'bad entity link: {r}')

    ev=read_csv(BASE/'evaluation/evaluation_questions.csv')
    known_docs=set(doc_ids)
    for r in ev:
        for d in [x.strip() for x in r['expected_documents'].split(';') if x.strip()]:
            if d not in known_docs: errors.append(f'{r["question_id"]}: unknown expected document {d}')
    routes={r['expected_route'] for r in ev}
    if not {'DOCUMENT_ONLY','SQL_ONLY','HYBRID'} <= routes: errors.append(f'evaluation missing one or more core routes: {routes}')

    print('AgentOps AI — Phase 0 Dataset Validation')
    print(f'Dataset: {BASE}')
    print(f'Tables: {len(tables)} | Rows: {sum(len(v) for v in tables.values())}')
    print(f'Documents: {len(docs)} | Metadata rows: {len(meta)} | Entity links: {len(links)}')
    print(f'Evaluation questions: {len(ev)} | Routes: {sorted(routes)}')
    if errors:
        print(f'\n{len(errors)} validation error(s):')
        for e in errors: print(' -', e)
        return 1
    print('\nPASS — Phase 0 dataset validation completed successfully.')
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
