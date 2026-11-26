#!/usr/bin/env node
"use strict";
const fs=require("node:fs");
const path=require("node:path");
const assert=require("node:assert/strict");
const {evaluate}=require("./procurement_gate.js");
const root=path.resolve(__dirname,"..");
const read=p=>fs.readFileSync(path.join(root,p),"utf8");
const data=JSON.parse(read("data/procurement/evidence.json"));
assert.equal(data.dataset,"procurement_evidence");
assert.ok(Array.isArray(data.records));
assert.equal(new Set(data.records.map(r=>r.id)).size,data.records.length);
const p={minimum_purchases:100,max_age_days:7,target_net_margin_pct:15,budget_min_rub:5000,budget_max_rub:300000,scenario_sales_pct:20};
assert.deepEqual(data.policy,p);
const gate=read("scripts/procurement_gate.js").trim();
assert.ok(read("web/procurement/index.html").includes(gate),"The browser must use the same gate");
const {execFileSync}=require("node:child_process");
const code=read("web/procurement/index.html").match(/<script>([\s\S]*?)<\/script>/)[1];
new Function(code); // Parse only; DOM smoke test is separate.
const day=process.argv[2]||new Date().toISOString().slice(0,10);
assert.match(day,/^\d{4}-\d{2}-\d{2}$/);
for(const r of data.records){assert.ok(r.id&&r.name&&r.model&&r.ru&&r.china&&r.economics);const result=evaluate(r,p,day);console.log(r.id,result.status,result.net_margin_pct??"—");}
const u="https://example.com/product/1",v="fixture-only",date=day;
const fixture={id:"test",name:"TEST ONLY",model:"TEST",variant_key:v,checked_at:date,review_status:"verified",ru:{url:u,image_url:u,image_status:"exact_photo_verified",availability_verified:true,demand:{value:300,type:"cumulative_purchases",verified:true,url:u,observed_at:date},offers:["A","B"].map((platform,i)=>({platform,url:u+"?"+i,price_rub:4000+i*200,currency:"RUB",price_type:"public_unconditional_retail_offer",in_stock:true,match_confidence:"exact_sku",variant_key:v,observed_at:date}))},china:{url:u,image_url:u,image_status:"exact_photo_verified",variant_key:v,match_verified:true,match_source_url:u,unit_rub:1000,moq:20,quote_quantity:20,quote_verified:true,quote_date:date,quote_valid_until:date,quote_source_url:u,supplier_verified:true},economics:{verified:true,checked_at:date,source_urls:[u],import_per_unit_rub:200,sales_fixed_per_unit_rub:100,sales_pct:20,taxes_per_unit_rub:100,other_per_unit_rub:100}};
const ok=evaluate(fixture,p,date);
assert.equal(ok.status,"approved");
assert.equal(ok.net_profit_rub,1700);
assert.equal(ok.average_offer_rub,4100);
for(const mut of [r=>r.economics.import_per_unit_rub=null,r=>r.ru.offers[1].platform="A",r=>r.ru.offers[0].price_type="conditional_yandex_pay",r=>r.china.variant_key="wrong",r=>r.ru.demand.type="reviews",r=>r.china.quote_valid_until="2000-01-01",r=>r.china.unit_rub=3500,r=>r.china.image_url=null,r=>r.china.quote_quantity=1000,r=>r.ru.offers[0].observed_at="2000-01-01"]){const copy=structuredClone(fixture);mut(copy);assert.notEqual(evaluate(copy,p,date).status,"approved");}
assert.notEqual(evaluate(fixture,p,"2099-01-01").status,"approved");
console.log("PASS: schema, shared gate, JS syntax, positive and negative eligibility fixtures");
