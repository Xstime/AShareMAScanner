"""Validate the embedded THS ranking parser without network or AKShare."""
from __future__ import annotations
import importlib.util
import io
import sys
import unittest
from pathlib import Path
from importlib.machinery import SourceFileLoader

source=Path(__file__).resolve().parents[1]/"A股MA扫描器_v1.2.8.pyw"
loader=SourceFileLoader("scanner_builtin_http_test",str(source))
spec=importlib.util.spec_from_loader(loader.name,loader)
scanner=importlib.util.module_from_spec(spec)
sys.modules[spec.name]=scanner
spec.loader.exec_module(scanner)

namespace={"__name__":"builtin_ths_parser_test"}
exec(scanner.BaoStockBackend.FUND_CHILD,namespace)


def page_html(index,total,records):
    rows=[]
    for rank,sector,value in records:
        rows.append(
            f'<tr><td>{rank}</td><td><a href="#industry">{sector}</a></td>'
            f'<td>42</td><td>1000</td><td>1%</td><td>50</td>'
            f'<td>20</td><td>{value}</td></tr>'
        )
    return (
        '<html><body><table><thead><tr><th>序号</th><th>行业</th><th>公司家数</th>'
        '<th>行业指数</th><th>阶段涨跌幅</th><th>流入资金(亿)</th>'
        '<th>流出资金(亿)</th><th>净额(亿)</th></tr></thead><tbody>'
        + "".join(rows) + '</tbody></table>'
        + f'<span class="page_info">{index}/{total}</span></body></html>'
    ).encode("gb18030")


class RankParserTest(unittest.TestCase):
    def setUp(self):
        self.pages=[
            page_html(1,2,[(1,"电池","14.53"),(2,"银行","13.50"),(3,"证券","3.02")]),
            page_html(2,2,[(4,"白色家电","3.01"),(5,"保险","2.02"),(6,"煤炭","-7.21")]),
        ]
        self.urls=[]

    def fake_open(self,request,timeout=12):
        url=request.full_url
        self.urls.append(url)
        index=1 if url.endswith("/board/5/") else 2 if url.endswith("/page/2/") else 0
        if index==0:raise AssertionError(url)
        return io.BytesIO(self.pages[index-1])

    def test_fetches_every_page_and_return_fields(self):
        rows=namespace["ths_rank_rows"](urlopen=self.fake_open)
        self.assertEqual(len(rows),6)
        self.assertEqual(rows[0],{"行业":"电池","净额":14.53})
        self.assertEqual(rows[5],{"行业":"煤炭","净额":-7.21})
        self.assertEqual(len(self.urls),2)
        self.assertEqual([r["行业"] for r in sorted(rows,key=lambda d:d["净额"],reverse=True)[:5]],
                         ["电池","银行","证券","白色家电","保险"])

    def test_reject_missing_page_counter(self):
        self.pages[1]=self.pages[1].replace(b'page_info',b'wrong_tag')
        with self.assertRaisesRegex(RuntimeError,"页码"):
            namespace["ths_rank_rows"](urlopen=self.fake_open)

    def test_reject_skipped_rank(self):
        self.pages[1]=page_html(2,2,[(5,"白色家电","3.01"),(6,"保险","2.02")])
        with self.assertRaisesRegex(RuntimeError,"不连续"):
            namespace["ths_rank_rows"](urlopen=self.fake_open)

    def test_reject_bad_numeric_value(self):
        self.pages[1]=page_html(2,2,[(4,"白色家电","—"),(5,"保险","2.02")])
        with self.assertRaisesRegex(RuntimeError,"净额格式"):
            namespace["ths_rank_rows"](urlopen=self.fake_open)

    def test_no_akshare_or_extra_html_parsers(self):
        child=scanner.BaoStockBackend.FUND_CHILD
        self.assertNotIn("import akshare as",child)
        self.assertNotIn("from bs4 import",child)
        self.assertNotIn("requests.get(",child)


if __name__=="__main__":
    unittest.main()
