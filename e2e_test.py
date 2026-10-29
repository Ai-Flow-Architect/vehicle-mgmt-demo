"""車両管理デモの通し試験（ログイン〜台帳〜修理登録〜集計〜権限まで）。
使い方: python3 e2e_test.py [URL]   既定はローカルの index.html（今日を 2026-10-29 に固定）
"""
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright

BASE = sys.argv[1] if len(sys.argv) > 1 else (Path(__file__).parent / "index.html").resolve().as_uri()
URL = BASE + "?today=2026-10-29"
SHOTS = Path(__file__).parent / "shots"
SHOTS.mkdir(exist_ok=True)
errors, results = [], []


def check(name, cond):
    results.append((name, bool(cond)))
    print(("OK  " if cond else "NG  ") + name)


def login(pg, email):
    pg.goto(URL + "#/login")
    pg.wait_for_selector("#loginBtn")
    pg.fill("#lemail", email)
    pg.fill("#lpw", "demo")
    pg.click("#loginBtn")
    pg.wait_for_selector("#kpiCount")


def num(s):
    return int("".join(ch for ch in s if ch.isdigit() or ch == "-") or 0)


with sync_playwright() as p:
    b = p.chromium.launch()
    # 端末がダークモードでも白いままか
    ctx = b.new_context(viewport={"width": 1280, "height": 900}, color_scheme="dark", accept_downloads=True, locale="ja-JP")
    pg = ctx.new_page()
    pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
    pg.goto(URL)
    pg.evaluate("localStorage.clear(); sessionStorage.clear()")
    pg.reload()
    pg.goto(URL + "#/login")
    pg.wait_for_selector("#loginBtn")
    bg = pg.evaluate("getComputedStyle(document.body).backgroundColor")
    check(f"ダーク端末でも背景は明るい ({bg})", bg in ("rgb(245, 247, 250)",))
    pg.screenshot(path=str(SHOTS / "00_login.png"))

    # ログイン失敗→成功
    pg.fill("#lemail", "admin@example.com")
    pg.fill("#lpw", "wrong")
    pg.click("#loginBtn")
    check("誤ったパスワードはエラー表示", pg.is_visible("text=メールアドレスかパスワードが違います"))
    pg.fill("#lpw", "demo")
    pg.click("#loginBtn")
    pg.wait_for_selector("#kpiCount")
    check("管理者のホーム 100台", pg.inner_text("#kpiCount") == "100台")
    check("期限切れ 2台", pg.inner_text("#kpiOver") == "2台")
    n30 = num(pg.inner_text("#kpi30"))
    check(f"30日以内 6台以上 ({n30})", n30 >= 6)
    check("管理者は6つの画面が見える", len(pg.query_selector_all("#nav a")) == 6)
    clip = pg.evaluate("[...document.querySelectorAll('.tbl-wrap')].filter(e=>e.scrollWidth>e.clientWidth+1).length")
    check(f"PCのホームで表が横に切れない (切れ={clip})", clip == 0)
    pg.screenshot(path=str(SHOTS / "01_home_admin.png"), full_page=True)

    # ホームの今年度費用＝データからの独立計算と一致
    exp = pg.evaluate("""() => { const S = JSON.parse(localStorage.getItem('vehicle_demo_v1'));
        return S.repairs.filter(r => r.date >= '2026-04-01' && r.date <= '2026-10-29').reduce((a, r) => a + r.cost, 0); }""")
    check(f"ホームの今年度費用が独立計算と一致 ({exp:,}円)", num(pg.inner_text("#kpiCost")) == exp)

    # 台帳：絞り込み
    pg.click("nav >> text=車両台帳")
    pg.wait_for_selector("#vList tr")
    check("台帳 初期100台", pg.inner_text("#vCount") == "100台を表示しています")
    pg.select_option("#fdiv", "物流部")
    c_div = num(pg.inner_text("#vCount"))
    check(f"事業部で絞り込み 物流部=12台 ({c_div})", c_div == 12)
    pg.select_option("#fcls", "4tトラック")
    c2 = num(pg.inner_text("#vCount"))
    rows = pg.query_selector_all("#vList tr[data-v]")
    check(f"区分で更に絞り込み ({c2}台・全行が4t)", c2 == len(rows) and all("4tトラック" in r.inner_text() for r in rows))
    pg.click("#fclear")
    pg.select_option("#finsp", "over")
    check("車検 期限切れで絞り込み 2台", pg.inner_text("#vCount") == "2台を表示しています")
    pg.click("#fclear")
    pg.fill("#fq", "エルフ")
    rows = pg.query_selector_all("#vList tr[data-v]")
    check(f"車名で検索（{len(rows)}台・全行にエルフ）", len(rows) > 0 and all("エルフ" in r.inner_text() for r in rows))
    pg.fill("#fq", "該当しない文字列")
    check("該当なしの案内", pg.is_visible("text=条件に合う車両がありません"))
    pg.click("#fclear")
    with pg.expect_download() as dl:
        pg.click("#csvV")
    path = dl.value.path()
    text = Path(path).read_text(encoding="utf-8-sig")
    check("台帳CSV 見出し＋100行", len(text.strip().splitlines()) == 101 and text.startswith("ナンバー,"))
    pg.screenshot(path=str(SHOTS / "02_vehicles.png"))

    # 車両の登録：入力漏れ→重複→成功
    pg.click("text=＋ 車両を登録")
    pg.click("#vsave")
    check("必須の入力漏れを全部表示", all(pg.is_visible(f"text={t}") for t in ["ナンバーを入力してください", "車名を入力してください", "車検満了日を入力してください"]))
    dup = pg.evaluate("JSON.parse(localStorage.getItem('vehicle_demo_v1')).vehicles[0].plate")
    pg.fill("#vplate", dup.replace(" ", ""))
    pg.fill("#vname", "テスト車")
    pg.select_option("#vcls", "2tトラック")
    pg.select_option("#vdiv", "工事部")
    pg.fill("#vdue", "2026-11-10")
    pg.click("#vsave")
    check("同じナンバー（空白違い）は重複エラー", pg.is_visible("text=同じナンバーの車両がすでに登録されています"))
    pg.fill("#vplate", "見本 100 て 99-01")
    pg.fill("#vname", "<b>テスト車</b>")
    pg.click("#vsave")
    pg.wait_for_selector("#vTitle")
    check("登録後に詳細へ・タグは文字のまま表示（XSS無効）", "<b>テスト車</b>" in pg.inner_text("#vTitle"))
    check("12日後の満了は あと12日", pg.inner_text("#vInsp") == "あと12日")
    new_vid = int(pg.url.split("/vehicle/")[1])

    # 修理・整備の登録：入力漏れ→車検で満了日更新
    pg.click("text=＋ 修理・整備を登録")
    pg.wait_for_selector("#rsave")
    check("種別が修理の時は次の車検欄を出さない", not pg.is_visible("#nextInspBox"))
    check("詳細から開くと車両が選択済み", pg.eval_on_selector("#rv", "e=>e.value") == str(new_vid))
    pg.fill("#rcost", "")
    pg.click("#rsave")
    check("費用・業者・箇所の入力漏れを表示", all(pg.is_visible(f"text={t}") for t in ["費用は0以上の整数（円）で入力してください", "業者を選んでください", "修理・整備した箇所を1つ以上選んでください"]))
    pg.fill("#rdate", "2026-11-05")
    pg.fill("#rcost", "98000")
    pg.click("#rsave")
    check("未来の日付は登録できない", pg.is_visible("text=未来の日付は登録できません"))
    pg.fill("#rdate", "2026-10-29")
    check("費用の円表示", pg.inner_text("#rcostLbl") == "98,000円")
    pg.click("#rkind >> text=車検")
    check("車検を選ぶと次回の満了日を自動提案（トラック=1年）", pg.eval_on_selector("#rnext", "e=>e.value") == "2027-11-10")
    pg.select_option("#rvendor", index=1)
    pg.click("#rparts >> text=ブレーキ")
    pg.click("#rparts >> text=その他")
    pg.screenshot(path=str(SHOTS / "03_repair_form.png"), full_page=True)
    pg.click("#rsave")
    pg.wait_for_selector("#hist")
    check("登録後 履歴に1件・98,000円", pg.is_visible("#hist >> text=98,000円"))
    check("車検満了日が 2027/11/10 に更新", pg.is_visible("text=2027/11/10"))

    # 記録の修正・削除
    pg.click("#hist >> text=直す")
    pg.fill("#rcost", "100000")
    pg.click("#rsave")
    pg.wait_for_selector("#hist")
    check("記録の修正が反映", pg.is_visible("#hist >> text=100,000円"))
    pg.click("#hist >> text=直す")
    pg.once("dialog", lambda d: d.accept())
    pg.click("#rdel")
    pg.wait_for_selector("text=まだ記録がありません。")
    check("記録の削除", True)

    # 集計
    pg.click("nav >> text=費用の集計")
    pg.wait_for_selector("#rTbl")
    exp_cur = pg.evaluate("""() => { const S = JSON.parse(localStorage.getItem('vehicle_demo_v1'));
        return S.repairs.filter(r => r.date >= '2026-04-01' && r.date <= '2026-10-29').reduce((a, r) => a + r.cost, 0); }""")
    exp_prev = pg.evaluate("""() => { const S = JSON.parse(localStorage.getItem('vehicle_demo_v1'));
        return S.repairs.filter(r => r.date >= '2025-04-01' && r.date <= '2025-10-29').reduce((a, r) => a + r.cost, 0); }""")
    check(f"今期合計が独立計算と一致 ({exp_cur:,}円)", num(pg.inner_text("#totCur")) == exp_cur)
    check(f"前年同期との差が一致 ({exp_cur - exp_prev:+,}円)", num(pg.inner_text("#totDiff")) == exp_cur - exp_prev)
    rows = pg.query_selector_all("#rTbl tr")
    check("事業部8行＋合計", len(rows) == 9)
    s = sum(num(r.query_selector_all("td")[1].inner_text()) for r in rows[:-1])
    check("事業部の合計＝合計行", s == num(rows[-1].query_selector_all("td")[1].inner_text()))
    butsu = [r for r in rows if r.inner_text().startswith("物流部")][0]
    check("物流部は前年より増加（赤字の＋表示）", "+" in butsu.query_selector_all("td")[3].inner_text())
    pg.screenshot(path=str(SHOTS / "04_report.png"), full_page=True)
    pg.click("#rcmp >> text=前年度の1年分")
    check("比較を前年度の1年分へ切替", "2026/03/31" in pg.inner_text("#periodLbl"))
    pg.select_option("#rby", "cls")
    check("区分ごとに切替", pg.is_visible("#rTbl >> text=4tトラック"))
    with pg.expect_download() as dl:
        pg.click("#csvR")
    t = Path(dl.value.path()).read_text(encoding="utf-8-sig")
    check("集計CSV 見出しと合計行", t.startswith("車両の区分,今期") and "合計," in t)

    # マスタ
    pg.click("nav >> text=業者・箇所の登録")
    pg.fill("#mvn", "テスト整備")
    pg.click("#mvadd")
    check("業者を追加", pg.is_visible("#vendList >> text=テスト整備"))
    pg.fill("#mvn", "テスト整備")
    pg.click("#mvadd")
    check("同名の業者は追加できない", pg.is_visible("text=同じ名前の業者がすでにあります"))
    check("使用中の業者は削除ボタンなし", pg.is_visible("#vendList >> text=使用中"))
    pg.click("nav >> text=利用者と権限")
    pg.wait_for_selector("[data-ur='1']")
    check("自分の権限は変更不可", pg.eval_on_selector("[data-ur='1']", "e=>e.disabled"))
    pg.click("text=ログアウト")

    # 事業部の担当：自分の事業部だけ
    login(pg, "koji@example.com")
    check("事業部担当のホームは工事部だけ (見本13台＋試験で登録1台=14台)", pg.inner_text("#kpiCount") == "14台")
    check("事業部担当には設定の画面が無い", len(pg.query_selector_all("#nav a")) == 4)
    pg.click("nav >> text=車両台帳")
    pg.wait_for_selector("#vList tr[data-v]")
    rows = pg.query_selector_all("#vList tr[data-v]")
    check("台帳は工事部の車両だけ (14台)", len(rows) == 14 and all("工事部" in r.inner_text() for r in rows))
    other = pg.evaluate("JSON.parse(localStorage.getItem('vehicle_demo_v1')).vehicles.find(v=>v.div==='物流部').id")
    pg.goto(URL + f"#/vehicle/{other}")
    check("他の事業部の車両はURL直打ちでも見えない", pg.is_visible("text=この画面を開く権限がありません"))
    pg.goto(URL + "#/master")
    check("マスタもURL直打ちで拒否", pg.is_visible("text=この画面を開く権限がありません"))
    pg.goto(URL + "#/repair/new")
    opts = pg.eval_on_selector_all("#rv optgroup", "els=>els.map(e=>e.label)")
    check("修理登録の車両一覧は工事部だけ", opts == ["工事部"])
    pg.click("text=ログアウト")

    # 閲覧のみ
    login(pg, "view@example.com")
    check("閲覧のみは全社101台が見える", pg.inner_text("#kpiCount") == "101台")
    check("閲覧のみには登録の画面が無い", not pg.is_visible("nav >> text=修理・整備の登録"))
    pg.goto(URL + "#/repair/new")
    check("閲覧のみは修理登録をURL直打ちでも拒否", pg.is_visible("text=この画面を開く権限がありません"))
    pg.goto(URL + "#/vehicle/1")
    check("閲覧のみの詳細に編集ボタンなし", not pg.is_visible("text=車両の情報を直す"))
    pg.click("text=ログアウト")

    # ===== 検査役の指摘の再現ケース（2026-10-29） =====
    login(pg, "admin@example.com")
    J = "JSON.parse(localStorage.getItem('vehicle_demo_v1'))"

    # 指摘5：ログアウトしても絞り込みが次の人に残らない
    pg.click("nav >> text=車両台帳")
    pg.wait_for_selector("#vList tr[data-v]")
    pg.select_option("#fdiv", "物流部")
    pg.fill("#fq", "エルフ")
    pg.click("text=ログアウト")
    login(pg, "koji@example.com")
    pg.click("nav >> text=車両台帳")
    pg.wait_for_selector("#vList tr[data-v]")
    check("ログアウト後、別の人に絞り込みが残らない", pg.input_value("#fq") == "" and len(pg.query_selector_all("#vList tr[data-v]")) == 14)
    pg.click("text=ログアウト")
    login(pg, "admin@example.com")

    # 指摘4：車検の年数（軽トラック=2年・バン=1年）と、満了日より前の受検は満了日から数える
    kt = pg.evaluate(J + ".vehicles.find(v=>v.cls==='軽トラック'&&v.status==='稼働')")
    pg.goto(URL + f"#/repair/new?v={kt['id']}")
    pg.wait_for_selector("#rsave")
    pg.click("#rkind >> text=車検")
    from datetime import date, timedelta
    due = date.fromisoformat(kt["inspDue"])
    today = date(2026, 10, 29)
    if today >= due - timedelta(days=30) and today <= due:
        exp_next = due.replace(year=due.year + 2)
    else:
        exp_next = today.replace(year=today.year + 2) - timedelta(days=1)
    check(f"軽トラックの次の車検は2年 ({exp_next})", pg.input_value("#rnext") == exp_next.isoformat())
    pg.fill("#rnext", "2028-01-31")
    pg.fill("#rdate", "2026-10-28")
    pg.dispatch_event("#rdate", "change")
    check("手で直した次の満了日は日付を変えても上書きしない", pg.input_value("#rnext") == "2028-01-31")
    bn = pg.evaluate(J + ".vehicles.find(v=>v.cls==='バン'&&v.status==='稼働')")
    pg.goto(URL + f"#/repair/new?v={bn['id']}")
    pg.wait_for_selector("#rsave")
    pg.click("#rkind >> text=車検")
    nxt = date.fromisoformat(pg.input_value("#rnext"))
    bdue = date.fromisoformat(bn["inspDue"])
    check(f"バンの次の車検は1年 ({nxt})", nxt in (bdue.replace(year=bdue.year + 1), today.replace(year=today.year + 1) - timedelta(days=1)))

    # 指摘3：車検の記録を消すと満了日が元に戻る
    before = bn["inspDue"]
    pg.fill("#rcost", "120000")
    pg.select_option("#rvendor", index=1)
    pg.click("#rparts >> text=その他")
    pg.click("#rsave")
    pg.wait_for_selector("#hist")
    after = pg.evaluate(J + f".vehicles.find(v=>v.id==={bn['id']}).inspDue")
    check(f"車検の登録で満了日が更新 ({before}→{after})", after != before)
    pg.click("#hist tr:first-child >> text=直す")
    pg.wait_for_selector("#rdel")
    check("車検の記録を直す画面に満了日の案内", pg.is_visible("#editInspNote"))
    pg.once("dialog", lambda d: d.accept())
    pg.click("#rdel")
    pg.wait_for_selector("#vTitle")
    back = pg.evaluate(J + f".vehicles.find(v=>v.id==={bn['id']}).inspDue")
    check(f"車検の記録を削除すると満了日が元に戻る ({back})", back == before)

    # 走行距離：記録に入れると車両の走行距離も進む
    pg.goto(URL + f"#/repair/new?v={bn['id']}")
    pg.wait_for_selector("#rsave")
    pg.fill("#rcost", "8000")
    pg.select_option("#rvendor", index=1)
    pg.click("#rparts >> text=オイル交換")
    pg.fill("#rmile", "999999")
    pg.click("#rsave")
    pg.wait_for_selector("#hist")
    check("走行距離が履歴と車両に反映", pg.is_visible("#hist >> text=999,999 km") and pg.is_visible("text=999,999 km"))

    # 指摘1：廃車にしてもホームと集計・台帳の数字が一致
    pg.goto(URL + f"#/vehicle/{bn['id']}/edit")
    pg.wait_for_selector("#vsave")
    pg.click("#vst >> text=廃車")
    pg.click("#vsave")
    pg.wait_for_selector("#vTitle")
    pg.goto(URL + "#/home")
    pg.wait_for_selector("#kpiCost")
    home_cost, home_over = num(pg.inner_text("#kpiCost")), num(pg.inner_text("#kpiOver"))
    pg.click("nav >> text=費用の集計")
    pg.wait_for_selector("#totCur")
    check(f"廃車ありでもホームの費用＝集計の合計 ({home_cost:,})", home_cost == num(pg.inner_text("#totCur")))
    pg.click("nav >> text=車両台帳")
    pg.wait_for_selector("#vList tr[data-v]")
    pg.select_option("#finsp", "over")
    check("廃車ありでも台帳の期限切れ＝ホームの期限切れ", num(pg.inner_text("#vCount")) == home_over)
    pg.click("#fclear")

    # 指摘2：前年度を選んでも比較が0円にならない
    pg.click("nav >> text=費用の集計")
    pg.wait_for_selector("#rfy")
    pg.select_option("#rfy", "2025")
    pg.wait_for_selector("#totCur")
    exp25 = pg.evaluate("() => { const S = " + J + "; return S.repairs.filter(r => r.date >= '2025-04-01' && r.date <= '2026-03-31').reduce((a, r) => a + r.cost, 0); }")
    exp24 = pg.evaluate("() => { const S = " + J + "; return S.repairs.filter(r => r.date >= '2024-04-01' && r.date <= '2025-03-31').reduce((a, r) => a + r.cost, 0); }")
    check(f"2025年度の合計が独立計算と一致 ({exp25:,})", num(pg.inner_text("#totCur")) == exp25)
    check(f"2025年度の比較（2024年度）が0円でなく一致 ({exp24:,})", exp24 > 0 and num(pg.inner_text("#totDiff")) == exp25 - exp24)
    check("過去の年度は「今期」と呼ばない", "2025年度：" in pg.inner_text("#periodLbl"))

    # 指摘13：CSVで数式として動かない
    pg.goto(URL + "#/vehicle/new")
    pg.wait_for_selector("#vsave")
    pg.fill("#vplate", "見本 100 て 99-02")
    pg.fill("#vname", "=1+1")
    pg.select_option("#vcls", "乗用車")
    pg.select_option("#vdiv", "管理部")
    pg.fill("#vdue", "2027-05-01")
    pg.click("#vsave")
    pg.wait_for_selector("#vTitle")
    pg.click("nav >> text=車両台帳")
    pg.wait_for_selector("#csvV")
    with pg.expect_download() as dl:
        pg.click("#csvV")
    t = Path(dl.value.path()).read_text(encoding="utf-8-sig")
    check("CSVの=で始まる値は先頭に ' を付ける", ",'=1+1," in t)

    # 指摘8：利用者の追加と削除
    pg.click("nav >> text=利用者と権限")
    pg.wait_for_selector("#uadd")
    pg.fill("#un", "戊川 三郎")
    pg.fill("#ue", "view@example.com")
    pg.click("#uadd")
    check("同じメールの利用者は追加できない", pg.is_visible("text=同じメールアドレスの利用者がすでにいます"))
    pg.fill("#un", "戊川 三郎")
    pg.fill("#ue", "butsuryu@example.com")
    pg.select_option("#urole", "div")
    pg.select_option("#udiv", "物流部")
    pg.click("#uadd")
    pg.wait_for_selector("#userList >> text=戊川 三郎")
    pg.click("text=ログアウト")
    login(pg, "butsuryu@example.com")
    check("追加した事業部の担当でログイン（物流部12台）", pg.inner_text("#kpiCount") == "12台")
    pg.click("text=ログアウト")
    login(pg, "admin@example.com")
    pg.click("nav >> text=利用者と権限")
    pg.wait_for_selector("#userList")
    pg.once("dialog", lambda d: d.accept())
    pg.click("#userList tr:has-text('戊川 三郎') >> text=削除")
    pg.wait_for_timeout(300)
    check("利用者を削除", not pg.is_visible("#userList >> text=戊川 三郎"))
    pg.click("text=ログアウト")

    # スマホ幅：横にはみ出さない
    m = b.new_context(viewport={"width": 390, "height": 844}, color_scheme="dark", is_mobile=True, has_touch=True, locale="ja-JP")
    mp = m.new_page()
    mp.on("pageerror", lambda e: errors.append(str(e)))
    mp.goto(URL + "#/login")
    mp.click("[data-quick='1']")
    mp.wait_for_selector("#kpiCount")
    for route, shot in [("#/home", "05_sp_home"), ("#/vehicles", "06_sp_vehicles"), ("#/repair/new", "07_sp_repair"), ("#/report", "08_sp_report")]:
        mp.goto(URL + route)
        mp.wait_for_timeout(300)
        sw = mp.evaluate("document.documentElement.scrollWidth")
        check(f"スマホで横はみ出しなし {route} ({sw}px)", sw <= 390)
        if route in ("#/home", "#/report"):
            clip = mp.evaluate("[...document.querySelectorAll('.tbl-wrap')].filter(e=>e.scrollWidth>e.clientWidth+1).length")
            check(f"スマホ {route} で表が横に切れない (切れ={clip})", clip == 0)
        mp.screenshot(path=str(SHOTS / f"{shot}.png"), full_page=True)

    # データを最初に戻す
    pg.goto(URL + "#/login")
    pg.once("dialog", lambda d: d.accept())
    pg.click("#resetData")
    n = pg.evaluate("JSON.parse(localStorage.getItem('vehicle_demo_v1')).vehicles.length")
    check("最初の状態に戻す（100台に戻る）", n == 100)

    check(f"画面のエラー 0件 {errors[:3]}", not errors)
    b.close()

ng = [n for n, ok in results if not ok]
print(f"\n{len(results) - len(ng)}/{len(results)} 合格")
sys.exit(1 if ng else 0)
