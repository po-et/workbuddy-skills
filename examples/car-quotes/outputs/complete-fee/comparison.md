# 两份报价核对

仅列示用户录入范围的金额；不验证报价真实性，不计算税率/APR，不排序、不推荐车型或融资

输入 SHA256：`5ec9f0756edfe86c832b88c5ffb58be4f8820a04164adf37e527b9c6054ece3e`

| 范围（元） | A | B | B − A |
|---|---|---|---|
| 购车款项 | 150000 | 150000 | 0 |
| 录入贷款费用 | 15000 | 16500 | 1500 |
| 购车款项加贷款费用 | 165000 | 166500 | 1500 |
| 年度能耗假设 | 1755 | 1755 | 0 |

## A

用户来源说明：合成报价 A：无真实商家、车型或个人数据

| 输入字段（JSON Pointer） | 录入值 | 状态 |
|---|---|---|
| /quotes/0/amounts/price | 150000 | 已录入 |
| /quotes/0/amounts/tax | 0 | 已录入 |
| /quotes/0/amounts/insurance | 0 | 已录入 |
| /quotes/0/amounts/plate | 0 | 已录入 |
| /quotes/0/amounts/addons | 0 | 已录入 |
| /quotes/0/finance/principal | 100000 | 已录入 |
| /quotes/0/finance/total_repay | 112000 | 已录入 |
| /quotes/0/finance/fees_outside_total | 3000 | 已录入 |
| /quotes/0/energy/annual_km | 15000 | 已录入 |
| /quotes/0/energy/consumption_per_100 | 15 | 已录入 |
| /quotes/0/energy/unit_price | null | 待补 |
| /quotes/0/energy/home_price | 0.6 | 已录入 |
| /quotes/0/energy/fast_price | 1.5 | 已录入 |
| /quotes/0/energy/home_share | 0.8 | 已录入 |

购车款项算式：`price + tax + insurance + plate + addons`

录入贷款费用算式：`total_repay - principal + fees_outside_total`

购车款项加贷款费用算式：`purchase + finance_fee (cash: purchase only)`

年度能耗假设算式：`annual_km / 100 * consumption_per_100 * (home_price * home_share + fast_price * (1 - home_share))`

## B

用户来源说明：合成报价 B：无真实商家、车型或个人数据

| 输入字段（JSON Pointer） | 录入值 | 状态 |
|---|---|---|
| /quotes/1/amounts/price | 150000 | 已录入 |
| /quotes/1/amounts/tax | 0 | 已录入 |
| /quotes/1/amounts/insurance | 0 | 已录入 |
| /quotes/1/amounts/plate | 0 | 已录入 |
| /quotes/1/amounts/addons | 0 | 已录入 |
| /quotes/1/finance/principal | 100000 | 已录入 |
| /quotes/1/finance/total_repay | 110500 | 已录入 |
| /quotes/1/finance/fees_outside_total | 6000 | 已录入 |
| /quotes/1/energy/annual_km | 15000 | 已录入 |
| /quotes/1/energy/consumption_per_100 | 15 | 已录入 |
| /quotes/1/energy/unit_price | 0.78 | 已录入 |
| /quotes/1/energy/home_price | null | 待补 |
| /quotes/1/energy/fast_price | null | 待补 |
| /quotes/1/energy/home_share | null | 待补 |

购车款项算式：`price + tax + insurance + plate + addons`

录入贷款费用算式：`total_repay - principal + fees_outside_total`

购车款项加贷款费用算式：`purchase + finance_fee (cash: purchase only)`

年度能耗假设算式：`annual_km / 100 * consumption_per_100 * unit_price`
