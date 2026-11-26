function evaluate(record,policy,asOf){
 const p=policy,r=record.ru||{},c=record.china||{},e=record.economics||{},d=r.demand||{};
 const finite=v=>typeof v==="number"&&Number.isFinite(v),pos=v=>finite(v)&&v>0;
 const url=v=>typeof v==="string"&&/^https:\/\/[a-z0-9.-]+(?::443)?(?:\/[^\s]*)?$/i.test(v)&&!v.includes("\\");
 const day=v=>typeof v==="string"&&/^\d{4}-\d{2}-\d{2}$/.test(v)?Date.parse(v):NaN;
 const age=v=>(day(asOf)-day(v))/86400000,fresh=v=>age(v)>=0&&age(v)<=p.max_age_days,round=v=>Math.round(v*100)/100;
 const reasons=[],variant=typeof record.variant_key==="string"&&record.variant_key.trim(),offers=Array.isArray(r.offers)?r.offers:[];
 const qualifying=offers.filter(o=>url(o.url)&&pos(o.price_rub)&&o.currency==="RUB"&&o.price_type==="public_unconditional_retail_offer"&&o.in_stock===true&&o.match_confidence==="exact_sku"&&variant&&o.variant_key===variant&&fresh(o.observed_at)&&typeof o.platform==="string"&&o.platform.trim());
 const byPlatform=new Map();for(const o of qualifying){const k=o.platform.trim().toLowerCase();if(!byPlatform.has(k)||byPlatform.get(k).price_rub>o.price_rub)byPlatform.set(k,o);}
 const comparable=[...byPlatform.values()],avg=comparable.length>=2?round(comparable.reduce((s,o)=>s+o.price_rub,0)/comparable.length):null,benchmark=comparable.length?Math.min(...comparable.map(o=>o.price_rub)):null;
 if(!fresh(record.checked_at))reasons.push("Исследование устарело");
 if(!variant||c.variant_key!==variant||c.match_verified!==true)reasons.push("Точный вариант и комплект Китай / РФ не сверены");
 if(!url(r.url)||r.availability_verified!==true||comparable.length<2)reasons.push("Нет двух свежих сопоставимых цен независимых площадок и подтверждённого наличия");
 if(d.verified!==true||d.type!=="cumulative_purchases"||!pos(d.value)||d.value<p.minimum_purchases||!url(d.url)||!fresh(d.observed_at))reasons.push("Нет свежего подтверждённого счётчика покупок SKU");
 if(!url(r.image_url)||r.image_status!=="exact_photo_verified"||!url(c.image_url)||c.image_status!=="exact_photo_verified")reasons.push("Нет двух проверенных фотографий точной модели");
 if(!url(c.url)||!pos(c.unit_rub)||!Number.isInteger(c.moq)||c.moq<1||c.quote_verified!==true||!fresh(c.quote_date)||!Number.isFinite(day(c.quote_valid_until))||day(c.quote_valid_until)<day(asOf)||c.supplier_verified!==true||!Number.isInteger(c.quote_quantity)||c.quote_quantity<c.moq||!url(c.quote_source_url)||!url(c.match_source_url))reasons.push("Нет действующей котировки, точного объёма партии и проверки поставщика");
 const costKeys=["import_per_unit_rub","sales_fixed_per_unit_rub","sales_pct","taxes_per_unit_rub","other_per_unit_rub"];
 const costs=e.verified===true&&fresh(e.checked_at)&&Array.isArray(e.source_urls)&&e.source_urls.length>0&&e.source_urls.every(url)&&costKeys.every(k=>finite(e[k])&&e[k]>=0)&&e.sales_pct<=100;
 if(!costs)reasons.push("Полная себестоимость и расходы не подтверждены");
 let net=null,margin=null,batch=null;
 if(costs&&pos(c.unit_rub)&&pos(benchmark)&&Number.isInteger(c.quote_quantity)&&c.quote_quantity>=1){
 net=round(benchmark*(1-e.sales_pct/100)-c.unit_rub-e.import_per_unit_rub-e.sales_fixed_per_unit_rub-e.taxes_per_unit_rub-e.other_per_unit_rub);margin=round(net/benchmark*100);batch=round((c.unit_rub+e.import_per_unit_rub)*c.quote_quantity);
 if(margin<p.target_net_margin_pct)reasons.push("Чистая расчётная маржа ниже цели");if(batch<p.budget_min_rub||batch>p.budget_max_rub)reasons.push("Проверенная партия вне бюджета");}
 const rejected=String(record.review_status||"").startsWith("reject");if(rejected)reasons.push("Исследователь отклонил предложение");
 const approved=reasons.length===0&&margin!==null&&batch!==null,base=pos(r.benchmark_rub)?r.benchmark_rub:null;
 const publicChinaFresh=fresh(c.public_price_checked_at)||fresh(c.quote_date),ruObserved=offers.some(o=>url(o.url)&&o.available_on_page===true&&fresh(o.observed_at)&&o.price_rub===base);
 const spread=base!==null&&pos(c.unit_rub)?round(base-c.unit_rub):null,targetSpace=spread!==null?round(base*(1-(p.scenario_sales_pct+p.target_net_margin_pct)/100)-c.unit_rub):null;
 const candidate=!approved&&!rejected&&fresh(record.checked_at)&&d.verified===true&&d.type==="cumulative_purchases"&&d.value>=p.minimum_purchases&&url(d.url)&&fresh(d.observed_at)&&url(r.url)&&url(r.image_url)&&["merchant_photo_observed","exact_photo_verified"].includes(r.image_status)&&ruObserved&&url(c.url)&&publicChinaFresh&&Number.isInteger(c.moq)&&c.moq>0&&targetSpace!==null&&targetSpace>0&&c.unit_rub*c.moq<=p.budget_max_rub;
 return {status:approved?"approved":candidate?"candidate":"archive",reasons,average_offer_rub:avg,benchmark_rub:benchmark,net_profit_rub:approved?net:null,net_margin_pct:approved?margin:null,batch_rub:approved?batch:null,observed_benchmark_rub:base,gross_difference_rub:spread,max_other_costs_for_target_margin_rub:targetSpace};
}
if(typeof module!=='undefined')module.exports={evaluate};
