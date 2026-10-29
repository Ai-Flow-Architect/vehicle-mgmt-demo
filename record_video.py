"""車両管理デモの操作録画（字幕つき mp4）。
使い方: python3 record_video.py [出力パス]
既定の出力: このフォルダの 車両管理デモ_操作説明.mp4
"""
import os
import pathlib
import sys

sys.path.insert(0, os.path.expanduser("~/.claude/skills/client-demo-video/scripts"))
import live_recorder as lr  # noqa: E402
from live_recorder import Rec, record  # noqa: E402

BASE = (pathlib.Path(__file__).parent / "index.html").resolve().as_uri() + "?today=2026-10-29"
OUT = sys.argv[1] if len(sys.argv) > 1 else str(pathlib.Path(__file__).parent / "車両管理デモ_操作説明.mp4")

# デモの主色（青）に合わせる＝説明カードと字幕の帯
lr.CARD_CSS = lr.CARD_CSS.replace("#00695c", "#1557ad").replace("#b2dfdb", "#cfe2fb")
_orig_ass = lr.write_ass


def _blue_ass(caps, total, path, w=1600, h=900):
    _orig_ass(caps, total, path, w, h)
    s = path.read_text(encoding="utf-8").replace("&H18404D00,&H18404D00", "&H10AD5715,&H10AD5715").replace("&HDBDFB2&", "&HFBE2CF&")
    path.write_text(s, encoding="utf-8")


lr.write_ass = _blue_ass

# 字幕は画面の中に表示して一緒に録画する（後から焼き込むと、録画のコマ落ちで後半ほど字幕がずれる＝2026-10-29 実測 144秒→137秒）
OVERLAY_JS = """([t, n]) => {
  let d = document.getElementById('__capbar');
  if (!d) { d = document.createElement('div'); d.id = '__capbar';
    d.style.cssText = 'position:fixed;left:50%;bottom:22px;transform:translateX(-50%);z-index:2147483640;' +
      'background:rgba(21,87,173,.96);color:#fff;padding:12px 26px;border-radius:10px;max-width:92%;' +
      'font:700 30px "Noto Sans CJK JP","Noto Sans JP",sans-serif;line-height:1.45;pointer-events:none;' +
      'box-shadow:0 4px 18px rgba(0,0,0,.25);text-align:center';
    (document.body || document.documentElement).appendChild(d); }
  d.innerHTML = '';
  const a = document.createElement('span'); a.style.color = '#cfe2fb'; a.textContent = '■ ' + t + '　';
  const b = document.createElement('span'); b.textContent = n;
  d.append(a, b);
  window.name = '__cap:' + JSON.stringify([t, n]);   // ページを移動しても字幕を引き継ぐ
}"""

# ページを読み込み直した時に、直前の字幕を出し直す
RESTORE_JS = "document.addEventListener('DOMContentLoaded', () => { if ((window.name || '').startsWith('__cap:')) {" \
             " (" + OVERLAY_JS + ")(JSON.parse(window.name.slice(6))); } });"


class SyncRec(Rec):
    cur = None

    def show(self):
        if self.cur:
            try:
                self.page.evaluate(OVERLAY_JS, list(self.cur))
            except Exception:  # noqa: BLE001
                pass

    def cap(self, title, note):
        super().cap(title, note)
        self.cur = (title, self.caps[-1][2])
        self.show()

    def card(self, title, body_html, sec):
        import re as _re
        body_html = _re.sub(r"<li>(.*?)</li>", lambda m: f"<li>{lr.end_mark(m.group(1))}</li>", body_html)
        self.page.set_content(f"<html><head><style>{lr.CARD_CSS}</style></head><body><div class='box'>"
                              f"<h1>{title}</h1>{body_html}</div></body></html>")
        self.show()
        self.hold(sec)


def _no_burned_caps(caps, total, path, w=1600, h=900):
    _blue_ass([], total, path, w, h)   # 焼き込む字幕は空（画面の中に出している）


lr.write_ass = _no_burned_caps


def scenario(r: Rec):
    p = r.page
    p.add_init_script(RESTORE_JS)
    r.cap("はじめに", "車両管理システムの試作デモを、実際に操作しながらご紹介します")
    r.card("社内車両管理システム　試作デモ",
           "<ul><li>ご依頼の6つの機能を、この順にお見せします</li>"
           "<li>表示している会社名・人名・車両はすべて架空です</li>"
           "<li>パソコンでもスマートフォンでも、ブラウザで使えます</li>"
           "<li>本番は、要件定義書と試作品を拝見してから御社に合わせてお作りします</li></ul>", 9)

    # ① ログインと権限
    p.goto(BASE)
    p.evaluate("localStorage.clear(); sessionStorage.clear()")
    p.goto(BASE + "#/login")
    p.reload()
    p.wait_for_selector("#loginBtn")
    r.cap("① ログイン", "メールアドレスとパスワードで入ります。違っていればその場でお知らせします")
    r.type(p.locator("#lemail"), "admin@example.com")
    r.type(p.locator("#lpw"), "wrong")
    r.click(p.locator("#loginBtn"))
    r.hold(1.5)
    r.type(p.locator("#lpw"), "demo")
    r.click(p.locator("#loginBtn"))
    p.wait_for_selector("#kpiCount")
    r.cap("ホーム画面", "車検の期限切れと、30日以内に車検を迎える車両がひと目で分かります")
    r.hold(3)
    p.mouse.move(800, 600, steps=10)
    p.mouse.wheel(0, 350)
    r.hold(3)
    r.cap("ホーム画面", "今年度の修理・整備費と、前年の同じ時期との増減も最初に出ます")
    p.mouse.wheel(0, -350)
    r.hold(3)

    # ② 台帳の検索と絞り込み
    r.click(p.locator("nav >> text=車両台帳"))
    p.wait_for_selector("#vList tr[data-v]")
    r.cap("② 車両台帳", "約100台を、車検の期限が近い順に一覧で表示します")
    r.hold(2.5)
    r.cap("② 事業部・区分で絞り込み", "事業部と車両の区分を選ぶだけで、すぐに絞り込めます")
    r.click(p.locator("#fdiv"))
    p.select_option("#fdiv", "物流部")
    r.hold(1.5)
    p.select_option("#fcls", "2tトラック")
    r.hold(2.5)
    r.click(p.locator("#fclear"))
    r.cap("② 検索", "ナンバーや車名の一部を入れると、その場で候補が絞られます")
    r.type(p.locator("#fq"), "エルフ")
    r.hold(2.5)
    r.click(p.locator("#fclear"))
    r.hold(1)

    # ③ 車両の登録（入力漏れは止める）
    r.cap("③ 車両の登録", "入力が足りない時は、何が足りないかを日本語でお伝えします")
    r.click(p.locator("text=＋ 車両を登録"))
    p.wait_for_selector("#vsave")
    r.click(p.locator("#vsave"))
    r.hold(2.5)
    r.type(p.locator("#vplate"), "見本 400 あ 12-34")
    r.type(p.locator("#vname"), "プロボックス")
    p.select_option("#vcls", "バン")
    r.hold(0.5)
    p.select_option("#vdiv", "工事部")
    r.hold(0.5)
    p.fill("#vdue", "2026-11-20")
    r.hold(0.5)
    r.type(p.locator("#vdriver"), "甲野")
    r.click(p.locator("#vsave"))
    p.wait_for_selector("#vTitle")
    r.cap("③ 車両の画面", "1台ごとに、車検の残り日数と修理・整備の費用と履歴がまとまります")
    r.hold(3)

    # ④ 修理・整備の登録と車検
    r.cap("④ 修理・整備の登録", "種別・業者・修理した箇所・費用を、押して選ぶだけで記録できます")
    r.click(p.locator("text=＋ 修理・整備を登録"))
    p.wait_for_selector("#rsave")
    r.type(p.locator("#rcost"), "98000")
    r.click(p.locator("#rkind >> text=車検"))
    r.hold(1)
    r.cap("④ 車検の記録", "車検を選ぶと、次の車検満了日を自動で計算します（手で直すこともできます）")
    p.locator("#nextInspBox").scroll_into_view_if_needed()
    r.hold(3)
    p.select_option("#rvendor", index=1)
    r.hold(0.6)
    r.click(p.locator("#rparts >> text=ブレーキ"))
    r.click(p.locator("#rparts >> text=タイヤ"))
    r.type(p.locator("#rmemo"), "車検と同時にブレーキパッドとタイヤを交換")
    r.click(p.locator("#rsave"))
    p.wait_for_selector("#hist")
    r.cap("④ 履歴に追加", "登録すると履歴に入り、車検満了日も新しい日付に変わります")
    r.hold(3.5)

    # ⑤ 修理業者・修理箇所の登録
    r.click(p.locator("nav >> text=業者・箇所の登録"))
    p.wait_for_selector("#mvadd")
    r.cap("⑤ 業者・箇所の登録", "修理業者と修理箇所は、管理者がこの画面で追加します")
    r.type(p.locator("#mvn"), "みなみ自動車サービス")
    r.type(p.locator("#mvt"), "000-0000-2001")
    r.click(p.locator("#mvadd"))
    r.hold(2)
    r.cap("⑤ 過去の記録を守る", "記録で使われている業者は、過去の記録が崩れないよう削除できません")
    r.hold(3)

    # ⑥ 修理費用の集計・前期比較
    r.click(p.locator("nav >> text=費用の集計"))
    p.wait_for_selector("#rTbl")
    r.cap("⑥ 修理費用の集計", "事業部ごとに、今期と前年の同じ時期の費用を並べて比べます")
    r.hold(3.5)
    p.mouse.move(800, 600, steps=10)
    p.mouse.wheel(0, 450)
    r.hold(3)
    r.cap("⑥ 前期との比較", "増えた所は赤、減った所は緑で表示し、増減の金額と割合も出します")
    r.hold(3)
    p.mouse.wheel(0, -450)
    r.hold(1)
    r.cap("⑥ 分け方を変える", "前年度の1年分との比較や、車両の区分ごと・業者ごとにも切り替えられます")
    r.click(p.locator("#rcmp >> text=前年度の1年分"))
    r.hold(2)
    r.click(p.locator("#rby"))
    p.select_option("#rby", "cls")
    r.hold(3)
    r.cap("⑥ CSVで保存", "表はCSVで保存でき、そのままExcelで開けます")
    r.click(p.locator("#csvR"))
    r.hold(2)

    # ⑦ 権限：利用者ごとに見える範囲が変わる
    r.click(p.locator("nav >> text=利用者と権限"))
    p.wait_for_selector("#userList")
    r.cap("⑦ 利用者と権限", "管理者・事業部の担当・閲覧のみの3つから、利用者ごとに権限を選べます")
    r.hold(3.5)
    r.click(p.locator("text=ログアウト"))
    p.wait_for_selector("#loginBtn")
    r.cap("⑦ 事業部の担当で入ると", "工事部の担当者には、工事部の車両だけが表示されます")
    r.type(p.locator("#lemail"), "koji@example.com")
    r.type(p.locator("#lpw"), "demo")
    r.click(p.locator("#loginBtn"))
    p.wait_for_selector("#kpiCount")
    r.hold(2)
    r.click(p.locator("nav >> text=車両台帳"))
    p.wait_for_selector("#vList tr[data-v]")
    r.hold(2.5)
    r.cap("⑦ 設定は管理者だけ", "担当者の画面には、業者の登録や権限の設定のメニューが出ません")
    r.hold(3)

    # まとめ
    r.cap("まとめ", "ご依頼の機能と、この動画の場面の対応です")
    p.goto("about:blank")
    r.card("ご依頼の機能 ⇔ この動画の場面",
           "<table>"
           "<tr><td>車両台帳の登録・編集・検索</td><td>② 台帳・③ 車両の登録</td></tr>"
           "<tr><td>車検期限、修理・整備履歴の管理</td><td>ホーム・③ 車両の画面・④ 修理と車検</td></tr>"
           "<tr><td>修理業者・修理箇所の登録</td><td>⑤ 業者・箇所の登録</td></tr>"
           "<tr><td>事業部別・車両区分別の絞り込み</td><td>② 絞り込み</td></tr>"
           "<tr><td>修理費用の集計・前期比較</td><td>⑥ 集計と比較・CSV</td></tr>"
           "<tr><td>ログイン認証・利用者ごとの権限管理</td><td>① ログイン・⑦ 権限</td></tr>"
           "</table>", 10)


if __name__ == "__main__":
    sys.exit(record(scenario, base=BASE, out=OUT, keep_dir=str(pathlib.Path(__file__).parent / "video_work"), rec_cls=SyncRec))
