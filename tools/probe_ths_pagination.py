"""Check THS industry page pagination without bypassing authentication or bot checks."""
import requests,re,time
from bs4 import BeautifulSoup
from urllib.parse import urljoin

UA="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0 Safari/537.36"
headers={"User-Agent":UA,"Referer":"https://q.10jqka.com.cn/thshy/"}
base="https://q.10jqka.com.cn"
sector="881121"
options=[
    f"/thshy/detail/code/{sector}/",
    f"/thshy/detail/code/{sector}/page/2/",
    f"/thshy/detail/page/2/code/{sector}/",
    f"/thshy/detail/field/199112/order/desc/page/2/code/{sector}/",
    f"/thshy/detail/field/199112/order/desc/page/2/ajax/0/code/{sector}/",
    f"/thshy/detail/field/199112/order/desc/page/2/ajax/1/code/{sector}/",
    f"/thshy/detail/code/{sector}/?page=2"
]
session=requests.Session()
for idx,path in enumerate(options):
    try:
        response=session.get(urljoin(base,path),headers=headers,timeout=12)
        soup=BeautifulSoup(response.text,"html.parser")
        tables=soup.find_all("table")
        stocks=[]
        for t in tables:
            for row in t.select("tbody tr"):
                cols=[x.get_text(strip=True) for x in row.find_all("td")]
                if len(cols)>1 and re.fullmatch(r"[0-9]{6}",cols[1]):
                    stocks.append(cols[1])
        info=[]
        if idx==0:
            for a in soup.select("a[href]"):
                href=a.get("href","")
                if "page" in href and ("thshy" in href or href.startswith("/") or href.startswith("?")):
                    info.append([a.get_text(strip=True)[:20],href[:160]])
            for pat in ("page_info","pageCount","totalPage","lastPage","1/10"):
                match=re.search(r".{0,50}"+re.escape(pat)+r".{0,70}",response.text,re.I)
                if match:info.append(["pattern",match.group(0)[:160]])
        print("CASE",idx,"STATUS",response.status_code,"BYTES",len(response.content),
              "STOCKS",len(stocks),"FIRST",stocks[:5],
              "LAST",stocks[-3:],"TITLE",(soup.title.get_text(strip=True)[:60] if soup.title else None),
              "INFO",info[:12],flush=True)
    except Exception as exc:
        print("CASE",idx,"ERROR",type(exc).__name__,str(exc)[:250],flush=True)
    time.sleep(.5)


print("BATTERY LAST-PAGE DIAGNOSTICS",flush=True)
for url in [
    "https://q.10jqka.com.cn/thshy/detail/code/881281/page/5/",
    "https://q.10jqka.com.cn/thshy/detail/code/881281/page/6/",
    "https://q.10jqka.com.cn/thshy/detail/page/6/code/881281/",
    "https://q.10jqka.com.cn/thshy/detail/code/881281/page/6/?r=1"
]:
    try:
        rr=requests.get(url,headers=headers,timeout=15)
        soup=BeautifulSoup(rr.text,"html.parser")
        trs=soup.select("table tbody tr")
        pager=soup.select_one(".page_info")
        text=soup.get_text(" ",strip=True)
        print("BATTERY",url,"STATUS",rr.status_code,"SIZE",len(rr.content),
              "ROWS",len(trs),"PAGE",pager.get_text(strip=True) if pager else "none",
              "TITLE",soup.title.get_text(strip=True) if soup.title else "none",
              "FIRST",text[:170],flush=True)
    except Exception as exc:
        print("BATTERY ERROR",type(exc).__name__,str(exc)[:250],flush=True)
    time.sleep(.5)
