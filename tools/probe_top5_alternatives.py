#!/usr/bin/env python3
"""Read-only real-cloud checks for same-source THS industry constituents.

Never stores user data, never assumes cross-provider industry labels match.
Each independent trial is subprocess-time-limited.
"""
import importlib.util
import json
import os
import sys
import subprocess
import time
import textwrap
from pathlib import Path

PROBE = r'''
import akshare as ak, json, traceback, sys, requests, re
kind = sys.argv[1]
sector = sys.argv[2] if len(sys.argv) > 2 else "银行"
print("AKSHARE_VERSION",getattr(ak,"__version__","unknown"),flush=True)
for symbol in ("stock_board_industry_name_ths", "stock_board_cons_ths", "stock_board_industry_cons_ths", "stock_board_industry_summary_ths"):
    print("AVAILABLE", symbol, hasattr(ak,symbol),flush=True)
try:
    if kind == "names":
        data = ak.stock_board_industry_name_ths()
        print("SHAPE",data.shape,"COLUMNS",list(data.columns),flush=True)
        print("HEAD",data.head(5).to_json(orient='records',force_ascii=False),flush=True)
        for label in ["银行","证券","煤炭开采加工","汽车整车","保险"]:
            mask = data.astype(str).apply(lambda col: col.str.contains(label, regex=False)).any(axis=1)
            print("MATCH", label,data[mask].head(3).to_json(orient='records',force_ascii=False),flush=True)
    elif kind == "summary":
        data=ak.stock_board_industry_summary_ths()
        print("SHAPE",data.shape,"COLUMNS",list(data.columns),flush=True)
        print("HEAD",data.head(5).to_json(orient='records',force_ascii=False),flush=True)
    elif kind == "boardcons":
        data=ak.stock_board_cons_ths(symbol=sector)
        print("SHAPE",data.shape,"COLUMNS",list(data.columns),flush=True)
        print("HEAD",data.head(3).to_json(orient='records',force_ascii=False),flush=True)
    elif kind == "industrycons":
        data=ak.stock_board_industry_cons_ths(symbol=sector)
        print("SHAPE",data.shape,"COLUMNS",list(data.columns),flush=True)
        print("HEAD",data.head(3).to_json(orient='records',force_ascii=False),flush=True)
    elif kind == "page":
        url="https://q.10jqka.com.cn/thshy/detail/code/" + sector + "/"
        r=requests.get(url,headers={"User-Agent":"Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/124.0 Safari/537.36","Referer":"https://q.10jqka.com.cn/thshy/"},timeout=15)
        print("HTTP",r.status_code, "URL",r.url, "BYTES",len(r.content), "TITLE",re.search(r"<title[^>]*>(.*?)</title>",r.text,re.S|re.I).group(1)[:120] if re.search(r"<title[^>]*>(.*?)</title>",r.text,re.S|re.I) else "none",flush=True)
        try:
            tables=__import__("pandas").read_html(__import__("io").StringIO(r.text))
            print("TABLES",len(tables),[(len(t), list(t.columns)) for t in tables[:4]],flush=True)
            for t in tables[:2]:
                print("HEAD",t.head(2).to_json(orient="records",force_ascii=False),flush=True)
        except Exception as exc:
            print("PARSE_ERROR",type(exc).__name__,str(exc)[:250],flush=True)
    elif kind == "ajax":
        url="https://q.10jqka.com.cn/thshy/detail/field/199112/order/desc/page/1/ajax/1/code/" + sector + "/"
        r=requests.get(url,headers={"User-Agent":"Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/124.0 Safari/537.36","Referer":"https://q.10jqka.com.cn/thshy/"},timeout=15)
        print("HTTP",r.status_code,"URL",r.url,"BYTES",len(r.content),"HAS_STOCK",bool(re.search(r"\\b(600|000)[0-9]{3}\\b",r.text)),"HTML",r.text[:190].replace("\n"," "),flush=True)
        try:
            tables=__import__("pandas").read_html(__import__("io").StringIO(r.text))
            print("TABLES",len(tables),[(len(t), list(t.columns)) for t in tables[:4]],flush=True)
        except Exception as exc:
            print("PARSE_ERROR",type(exc).__name__,str(exc)[:250],flush=True)
except Exception as exc:
    print("ERROR",type(exc).__name__,str(exc)[:500],flush=True)
    traceback.print_exc(limit=3)
'''
cases=[("names", ""),("summary",""),("boardcons","881121"),("industrycons","银行"),("page","881121"),("ajax","881121")];
print("Alternate same-provider THS industry membership checks:",flush=True)
for kind,sector in cases:
    start=time.monotonic()
    try:
        done=subprocess.run([sys.executable,"-c",PROBE,kind,sector],stdout=subprocess.PIPE,stderr=subprocess.PIPE,
                            encoding="utf-8",errors="replace",timeout=50,check=False)
        output=done.stdout
        error=done.stderr
        print("CASE",kind,sector,"ELAPSED",round(time.monotonic()-start,2),"RC",done.returncode,flush=True)
        for line in output.splitlines():
            if line.startswith("AVAILABLE"): continue
            print("RESULT",line[:1350],flush=True)
        if error:
            print("STDERR",error[-650:].replace("\n"," | "),flush=True)
    except subprocess.TimeoutExpired:
        print("CASE",kind,sector,"TIMEOUT 50s",flush=True)
