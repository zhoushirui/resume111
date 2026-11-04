from fastapi import FastAPI
from pydantic import BaseModel
import requests
from bs4 import BeautifulSoup
import re
import urllib.parse
import json
import time
import base64

app = FastAPI()



class ScrapeRequest(BaseModel):
    targets: str


def parse_target_line(query_text):
    """兼容“单位 姓名”和制表符分隔的“单位 姓名 职务”。"""
    columns = [column.strip() for column in re.split(r"\t+", query_text) if column.strip()]
    if len(columns) >= 2:
        return columns[0], columns[1], " ".join(columns[2:])

    parts = query_text.split()
    if len(parts) >= 2:
        return parts[0], parts[1], " ".join(parts[2:])
    return "", query_text.strip(), ""


def build_match_keywords(unit, role):
    keywords = []

    def add(value):
        value = value.strip(" ，,、")
        if len(value) >= 3 and value not in keywords:
            keywords.append(value)

    add(role)
    for part in re.split(r"[，,、；;]", role):
        add(part)

    add(unit)
    unit_without_party = re.sub(r"^中共", "", unit)
    add(unit_without_party)
    add(unit_without_party.replace("北京市委员会", "北京市委"))
    add(unit_without_party.replace("北京市委政法委员会", "北京市委政法委"))

    for short_name in ("宣传部", "政法委", "组织部", "统战部", "办公厅", "委员会"):
        if short_name in unit or short_name in role:
            add(short_name)

    return keywords


def normalized_match_text(value):
    return re.sub(r"[^\w\u4e00-\u9fff]", "", value or "")


def scrape_baike_wap(query_text, headers, forced_lemma_id=None):
    """通过百度百科移动页匹配同名词条并提取正文。"""
    unit, name, role = parse_target_line(query_text)
    match_keywords = build_match_keywords(unit, role)

    safe_name = urllib.parse.quote(name)
    mobile_headers = {
        **headers,
        "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 18_6 like Mac OS X) "
                      "AppleWebKit/605.1.15 Version/18.0 Mobile/15E148 Safari/604.1",
        "Accept-Language": "zh-CN,zh;q=0.9",
        "Referer": "https://www.baidu.com/",
    }

    try:
        target_url = f"https://wapbaike.baidu.com/item/{safe_name}"
        if forced_lemma_id:
            target_url += f"/{forced_lemma_id}"
        response = requests.get(target_url, headers=mobile_headers, timeout=30)
        response.encoding = "utf-8"
        if response.status_code != 200:
            return None, None, None, f"百度百科移动页请求失败，状态码: {response.status_code}"

        soup = BeautifulSoup(response.text, "html.parser")
        data_tag = soup.find("script", id="__NEXT_DATA__")
        if not data_tag or not data_tag.string:
            return None, None, None, "百度百科移动页缺少词条数据。"

        page_data = json.loads(data_tag.string)["props"]["pageProps"]["pageData"]
        current_lemma_id = page_data.get("lemmaId")
        selected_lemma_id = forced_lemma_id or current_lemma_id

        if forced_lemma_id and page_data.get("lemmaTitle") != name:
            return None, None, None, f"搜索结果词条【{page_data.get('lemmaTitle', '')}】与姓名【{name}】不符。"

        if match_keywords and not forced_lemma_id:
            candidates = [{
                "lemmaId": current_lemma_id,
                "lemmaDesc": page_data.get("lemmaDesc", ""),
            }]
            candidates.extend(page_data.get("navigation", {}).get("lemmas", []))

            best_candidate = None
            best_score = 0
            for lemma in candidates:
                desc = normalized_match_text(lemma.get("lemmaDesc", ""))
                score = sum(
                    len(normalized_match_text(keyword))
                    for keyword in match_keywords
                    if normalized_match_text(keyword) in desc
                )
                if score > best_score:
                    best_score = score
                    best_candidate = lemma

            if not best_candidate:
                return None, None, None, f"未找到与【{unit} {role}】匹配的同名百科词条。"

            selected_lemma_id = best_candidate.get("lemmaId")
            print(f"[爬虫监控] 移动版命中准确同名词条: {best_candidate.get('lemmaDesc', '')}")

        target_url = f"https://wapbaike.baidu.com/item/{safe_name}/{selected_lemma_id}"
        if selected_lemma_id != current_lemma_id:
            response = requests.get(target_url, headers=mobile_headers, timeout=30)
            response.encoding = "utf-8"
            if response.status_code != 200:
                return None, None, None, f"准确百科词条请求失败，状态码: {response.status_code}"
            soup = BeautifulSoup(response.text, "html.parser")

        main_content_div = soup.find("div", class_=re.compile(r"^index_pageContent__"))
        if not main_content_div:
            return None, None, target_url, "百科移动页已打开，但未找到正文内容。"

        for unwanted in main_content_div.find_all(["script", "style", "sup"]):
            unwanted.decompose()

        extracted_text = main_content_div.get_text(separator="\n", strip=True)
        extracted_text = re.sub(r"\[\d+(?:[,、-]\d+)*\]", "", extracted_text)
        extracted_text = "\n".join(
            line for line in extracted_text.splitlines()
            if line.strip() and not re.fullmatch(r"\d+", line.strip())
        )

        img_b64 = None
        img_tag = soup.find("img", src=re.compile(r"bkimg\.cdn\.bcebos\.com/pic/"))
        if img_tag and img_tag.get("src"):
            img_resp = requests.get(img_tag["src"], headers=mobile_headers, timeout=30)
            if img_resp.status_code == 200:
                img_b64 = "data:image/jpeg;base64," + base64.b64encode(img_resp.content).decode("utf-8")

        return extracted_text, img_b64, target_url, None
    except Exception as e:
        return None, None, None, f"百度百科移动页提取失败: {str(e)}"


# ================= 模块一：百度百科底层爬虫 (照片暴力提取版) =================
def scrape_baike_data(query_text):
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8"
    }
    target_url = None
    unit, name, role = parse_target_line(query_text)

    # 移动版页面可直接返回正文，并能从同名词条列表中按单位精确匹配。
    wap_text, wap_image, wap_url, wap_error = scrape_baike_wap(query_text, headers)
    if wap_text:
        print(f"[爬虫监控] 最终抓取目标: {wap_url}")
        print(f"[爬虫监控] ✅ 移动版成功提取正文，共 {len(wap_text)} 个字符。")
        if wap_image:
            print("[爬虫监控] ✅ 成功抓取人物照片！")
        return f"来源链接：{wap_url}\n{wap_text}", wap_image, None

    print(f"[爬虫监控] 移动版提取未成功，转入原网页兼容模式: {wap_error}")

    # 引擎 1：大搜索精准引流
    search_keyword = urllib.parse.quote(" ".join(part for part in (name, unit, "百度百科") if part))
    search_url = f"https://www.baidu.com/s?wd={search_keyword}"
    try:
        print(f"[爬虫监控] 正在通过百度大搜索引流: {query_text}")
        search_resp = requests.get(search_url, headers=headers, timeout=30)
        search_soup = BeautifulSoup(search_resp.text, 'html.parser')
        for tag in search_soup.find_all(attrs={"mu": True}):
            mu_url = tag.get('mu', '')
            if "baike.baidu.com/item/" in mu_url:
                item_match = re.search(r"baike\.baidu\.com/item/([^/?#]+)", mu_url)
                item_title = urllib.parse.unquote(item_match.group(1)) if item_match else ""
                if item_title != name:
                    continue
                target_url = mu_url
                print(f"[爬虫监控] 引擎1命中精准链接: {target_url}")
                break
    except Exception as e:
        print(f"[爬虫监控] 百度搜索引流失败，准备转入备用引擎: {e}")

    # 引擎 2：百科站内兜底
    if not target_url:
        print(f"[爬虫监控] 启用备用引擎...")
        keywords = build_match_keywords(unit, role)

        safe_name = urllib.parse.quote(name)
        item_url = f"https://baike.baidu.com/item/{safe_name}"

        try:
            response = requests.get(item_url, headers=headers, allow_redirects=True, timeout=30)
            response.encoding = 'utf-8'
            soup = BeautifulSoup(response.text, 'html.parser')

            script_match = re.search(r'window\.PAGE_DATA=\s*({.+?})\s*</script>', response.text, re.DOTALL)
            if script_match:
                page_data = json.loads(script_match.group(1))
                lemmas = page_data.get("navigation", {}).get("lemmas", [])

                if lemmas and keywords:
                    for lemma in lemmas:
                        desc = normalized_match_text(lemma.get("lemmaDesc", ""))
                        if any(normalized_match_text(keyword) in desc for keyword in keywords):
                            target_url = f"https://baike.baidu.com/item/{safe_name}/{lemma.get('lemmaId')}"
                            break
                else:
                    desc = page_data.get("lemmaDesc", "")
                    if not keywords or any(normalized_match_text(keyword) in normalized_match_text(desc) for keyword in keywords):
                        target_url = response.url
            if not target_url:
                target_url = response.url
        except Exception as e:
            return None, None, f"获取百科链接失败: {str(e)}"

    # ================= 提取正文与照片 =================
    if not target_url:
        return None, None, f"未能在百科找到符合【{query_text}】的准确履历。"

    lemma_id_match = re.search(r"baike\.baidu\.com/item/[^/?#]+/(\d+)", target_url)
    if lemma_id_match:
        wap_text, wap_image, wap_url, wap_error = scrape_baike_wap(
            query_text, headers, forced_lemma_id=lemma_id_match.group(1)
        )
        if wap_text:
            print(f"[爬虫监控] 最终抓取目标: {wap_url}")
            print(f"[爬虫监控] ✅ 移动版成功提取正文，共 {len(wap_text)} 个字符。")
            if wap_image:
                print("[爬虫监控] ✅ 成功抓取人物照片！")
            return f"来源链接：{wap_url}\n{wap_text}", wap_image, None
        print(f"[爬虫监控] 精准链接移动版提取失败: {wap_error}")

    try:
        if target_url.startswith("http:"):
            target_url = target_url.replace("http:", "https:")

        print(f"[爬虫监控] 最终抓取目标: {target_url}")
        response = requests.get(target_url, headers=headers, timeout=30)
        response.encoding = 'utf-8'
        soup = BeautifulSoup(response.text, 'html.parser')

        # --- 📸 核心修复：源码级暴力扫描图片 ---
        img_b64 = None
        try:
            img_url = None

            # 策略1：先在解析好的 HTML 树里直接找百度的图
            img_tag = soup.find('img', src=re.compile(r"bkimg\.cdn\.bcebos\.com/pic/"))
            if img_tag and img_tag.has_attr('src'):
                img_url = img_tag['src']

            # 策略2：如果被 JS 隐藏了，直接对网页的原始字符串进行“暴力正则扫描”
            if not img_url:
                # 兼容正常链接和被 JSON 反斜杠转义的隐藏链接 (\/)
                pic_match = re.search(r'(https:[\/\\]*bkimg\.cdn\.bcebos\.com[\/\\]*pic[\/\\]*[a-zA-Z0-9]+)',
                                      response.text)
                if pic_match:
                    # 剥离多余的转义符，还原纯净 URL
                    img_url = pic_match.group(1).replace('\\/', '/')

            # 如果找到了图片链接，执行下载
            if img_url:
                if img_url.startswith('//'):
                    img_url = 'https:' + img_url

                # 强制加上百科的压缩参数，防止原图太大导致前端加载卡顿
                if "?" not in img_url:
                    img_url += "?x-bce-process=image/resize,m_lfit,limit_1,w_536"

                img_resp = requests.get(img_url, headers=headers, timeout=30)
                if img_resp.status_code == 200:
                    img_b64 = "data:image/jpeg;base64," + base64.b64encode(img_resp.content).decode('utf-8')
                    print(f"[爬虫监控] ✅ 成功抓取人物照片！")
                else:
                    print(f"[爬虫监控] ❌ 图片请求失败，状态码: {img_resp.status_code}")
            else:
                print("[爬虫监控] ⚠️ 网页源代码中未找到任何百科图片链接")
        except Exception as e:
            print(f"[爬虫监控] ❌ 照片提取过程发生异常: {e}")

        # --- 提取文本 ---
        main_content_div = soup.find('div', class_=re.compile(r"^mainContent"))
        if main_content_div:
            extracted_text = main_content_div.get_text(separator="\n", strip=True)
            extracted_text = re.sub(r'\[\d+(?:[,、-]\d+)*\]', '', extracted_text)
            return f"来源链接：{response.url}\n{extracted_text}", img_b64, None
        else:
            return None, img_b64, "网页抓取成功，但未找到正文内容。"
    except Exception as e:
        return None, None, f"网络异常: {str(e)}"


@app.post("/api/scrape")
def api_scrape(req: ScrapeRequest):
    print(f"\n[后端监控] 👉 收到前端抓取请求：{req.targets}")
    lines = [line.strip() for line in re.split(r'[\n]', req.targets) if line.strip()]
    if not lines:
        return {"success": False, "error": "前端未传入有效目标"}

    all_raw_texts = []
    all_images = []

    for line in lines:
        raw_text, img_b64, err_msg = scrape_baike_data(line)
        if raw_text:
            all_raw_texts.append(f"【{line} 原始数据】：\n{raw_text}")
        else:
            all_raw_texts.append(f"【{line} 抓取失败】：\n{err_msg}")

        if img_b64:
            _, person_name, _ = parse_target_line(line)
            all_images.append({"name": person_name, "b64": img_b64})

        time.sleep(1.5)

    combined_raw_text = "\n\n======\n\n".join(all_raw_texts)
    print(f"[后端监控] ✅ 抓取完成，共提取到 {len(all_images)} 张照片。")
    return {"success": True, "content": combined_raw_text, "images": all_images}



