"""Diagnostic: can standard-library HTTP/HTML replace the only AKShare method?

Only public HTML pages; no auth/header spoof to bypass access restrictions.
Tests a small set of paths once, reports status, table structure, and rows.
"""
import html
import re
import urllib.request
from html.parser import HTMLParser


class TableProbe(HTMLParser):
    def __init__(self):
        super().__init__()
        self.rows=[];self.row=[];self.cell=[];self.inrow=False;self.incell=False
    def handle_starttag(self,tag,attrs):
        if tag=="tr":
            self.inrow=True;self.row=[]
        elif tag in ("td","th") and self.inrow:
            self.incell=True;self.cell=[]
    def handle_endtag(self,tag):
        if tag in ("td","th") and self.incell:
            self.row.append("".join(self.cell).strip())
            self.incell=False
        elif tag=="tr" and self.inrow:
            if self.row:self.rows.append(self.row)
            self.inrow=False
    def handle_data(self,data):
        if self.incell:self.cell.append(data)

base="https://data.10jqka.com.cn/funds/hyzjl/"
paths=[
    "board/5/",
    "board/5/page/1/",
    "board/5/field/tradezdf/order/desc/page/1/",
    "board/5/field/tradezdf/order/desc/page/1/ajax/1/free/1/",
    "board/5/field/tradezdf/order/desc/page/2/",
    "board/5/field/tradezdf/order/desc/page/2/ajax/1/free/1/",
]
for path in paths:
    url=base+path
    try:
        req=urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0","Accept":"text/html","Referer":base})
        with urllib.request.urlopen(req,timeout=13) as res:
            body=res.read(1_500_000).decode("utf-8",errors="replace")
            status=res.status
        parser=TableProbe()
        parser.feed(body)
        lines=[r for r in parser.rows if any("净额" in c or "资金" in c for c in r)]
        print("CASE",path,"HTTP",status,"LENGTH",len(body),"ROWS",len(parser.rows),
              "META",lines[:2],"SAMPLE",parser.rows[:4],"TOP5_HAS",["银行" in body,"电池" in body],
              "PAGES",re.findall(r'page_info[^>]*>([^<]+)',body)[:2],flush=True)
    except Exception as e:
        print("CASE",path,"ERROR",type(e).__name__,str(e)[:180],flush=True)
