#!/usr/bin/env python3
"""Only evidence-backed SKUs may appear in Product Radar's public ranking."""
import json
import sys
from pathlib import Path
from urllib.parse import urlsplit
from datetime import date

def https_url(value):
    if not isinstance(value,str) or not value.strip():
        return False
    u=urlsplit(value)
    return u.scheme=="https" and bool(u.netloc)

def validate(cat_path,products_path):
    errors=[]
    c=json.loads(Path(cat_path).read_text(encoding="utf-8"))
    p=json.loads(Path(products_path).read_text(encoding="utf-8"))
    categories=c.get("categories",[])
    if len(categories)<1:
        errors.append("No verified categories")
    last_turnover=float("inf")
    used=set()
    for rank,x in enumerate(categories,1):
        if x.get("rank")!=rank: errors.append(f"Category rank {rank} is inconsistent")
        if x.get("id") in used: errors.append("Duplicate category id")
        used.add(x.get("id"))
        t=x.get("turnover_billion_rub")
        if not isinstance(t,(int,float)) or t<=0 or t>last_turnover:
            errors.append(f"Category rank/turnover invalid: {x.get('id')}")
        else:last_turnover=t
        s=x.get("share_percent")
        if not isinstance(s,(int,float)) or not(0<s<=100):errors.append("Invalid category share")
    if not https_url(c.get("source_url")):errors.append("Missing official/reported category source")
    products=p.get("products")
    if not isinstance(products,list):errors.append("products must be a list");products=[]
    ids=set()
    required=("id","name","category","product_url","image_url","image_source_url","image_source_title","evidence_source_url","evidence_metric","evidence_value","evidence_date")
    for x in products:
        name=x.get("id","<missing>") if isinstance(x,dict) else "<invalid>"
        if not isinstance(x,dict):errors.append("Non-object product");continue
        if name in ids:errors.append("Duplicate product "+name)
        ids.add(name)
        for k in required:
            if not isinstance(x.get(k),str) or not x[k].strip():errors.append(f"{name}: missing {k}")
        for k in ("product_url","image_url","image_source_url","evidence_source_url"):
            if not https_url(x.get(k)):errors.append(f"{name}: invalid HTTPS {k}")
        try: date.fromisoformat(x["evidence_date"])
        except (KeyError,ValueError,TypeError):errors.append(f"{name}: invalid evidence date")
        if x.get("evidence_type") not in ("documented_units_sold","documented_revenue","documented_bestseller_position"):
            errors.append(f"{name}: unsupported evidence_type")
        if x.get("image_url","").lower().split("?")[0].endswith(".svg"):
            errors.append(f"{name}: SVG not a product photo")
    return errors,len(categories),len(products)

if __name__=="__main__":
    c=sys.argv[1] if len(sys.argv)>1 else "data/verified/categories.json"
    p=sys.argv[2] if len(sys.argv)>2 else "data/verified/products.json"
    errors,n,m=validate(c,p)
    if errors:
        print("REJECTED:\n"+"\n".join(errors));sys.exit(1)
    print(f"VERIFIED CATALOGUE VALID: {n} categories, {m} evidence-backed SKU. Empty SKU list is valid when sales evidence is absent.")
