"""Test full THS 5-day fund ranking + full same-source industry membership."""
import akshare as ak
import re
import requests
import pandas as pd
import time
from bs4 import BeautifulSoup

def get_codes_from_page(session,sector_code,page):
    # Unauthenticated public HTML page; avoid legacy AJAX paths requiring auth.
    url=(f"https://q.10jqka.com.cn/thshy/detail/code/{sector_code}/" if page==1
         else f"https://q.10jqka.com.cn/thshy/detail/code/{sector_code}/page/{page}/")
    r=session.get(url,timeout=14,headers={
        "User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0 Safari/537.36",
        "Referer":"https://q.10jqka.com.cn/thshy/"})
    r.raise_for_status()
    soup=BeautifulSoup(r.text,"html.parser")
    infos=soup.select(".page_info")
    total = None
    if infos:
        match=re.fullmatch(r"\s*(\d+)\s*/\s*(\d+)\s*",infos[0].get_text(strip=True))
        if not match:
            raise RuntimeError("unrecognized pagination "+str(infos[0].get_text(strip=True)))
        actual,total=map(int,match.groups())
        if actual!=page or total<=0 or total>100:
            raise RuntimeError(f"page counter mismatch {actual}/{total} expected {page}")
    table=None
    for current in soup.select("table"):
        names=[cell.get_text(strip=True) for cell in current.select("thead th")]
        if "代码" in names and "名称" in names:
            table=current
            break
    if table is None:
        raise RuntimeError("no constituent table (possible bot response)")
    codes=[]
    for tr in table.select("tbody tr"):
        cells=tr.select("td")
        if len(cells)<3: continue
        code=cells[1].get_text(strip=True)
        if re.fullmatch(r"\d{6}",code):
            codes.append(code)
    if not codes:
        raise RuntimeError("empty constituent table")
    if total is None and page==1 and len(codes)<20:
        total=1
    return total,codes

rank=ak.stock_fund_flow_industry(symbol="5日排行")
names=ak.stock_board_industry_name_ths()
assert {"行业","净额","公司家数"}.issubset(rank.columns),list(rank.columns)
assert {"name","code"}.issubset(names.columns),list(names.columns)
rank=rank.sort_values("净额",ascending=False).head(5)
mapping=dict(zip(names["name"].astype(str).str.strip(),names["code"].astype(str)))
print("LIVE 5D TOP5",rank[["行业","净额","公司家数"]].to_json(orient="records",force_ascii=False),flush=True)
for _,rec in rank.iterrows():
    sector=str(rec["行业"]).strip()
    code=mapping.get(sector)
    expected=int(rec["公司家数"])
    if not code:
        print("RESULT",sector,"FAIL sector name absent from same-provider code list",flush=True)
        continue
    found=set()
    try:
        with requests.Session() as sess:
            page_count,first=get_codes_from_page(sess,code,1)
            found.update(first)
            print("START",sector,code,"PAGES",page_count,"EXPECTED",expected,"FIRST",len(first),flush=True)
            for p in range(2,page_count+1):
                current_total,codes=get_codes_from_page(sess,code,p)
                if current_total is not None and current_total!=page_count:
                    raise RuntimeError(f"page count shifted {page_count}->{current_total}")
                if current_total is None and p!=page_count:
                    raise RuntimeError(f"missing pagination before final page {p}")
                if len(found.intersection(codes))>0:
                    raise RuntimeError(f"duplicate stocks between pages: {len(found.intersection(codes))}")
                found.update(codes)
                if p==page_count or p%4==0:
                    print("PAGE",sector,p,"/",page_count,"COUNT",len(found),flush=True)
                time.sleep(.15)
        print("RESULT",sector,"COMPLETE" if len(found)>0 else "EMPTY",
              "GOT",len(found),"REFERENCE_COMPANIES",expected,
              "COUNT_NOTE","mismatch" if len(found)!=expected else "matched",
              "FIRST_CODES",sorted(found)[:4],flush=True)
    except Exception as exc:
        print("RESULT",sector,"FAIL",type(exc).__name__,str(exc)[:400],
              "PARTIAL",len(found),flush=True)
