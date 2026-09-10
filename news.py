import io
import os
import urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed
import streamlit as st
import feedparser
import trafilatura
from bs4 import BeautifulSoup
import requests

st.set_page_config(page_title="穩定多元閱讀教材彙整工具", page_icon="📚", layout="centered")

st.title("📚 穩定多元閱讀教材彙整工具")
st.markdown("已全面修復 PDF 字型綁定，徹底消除方框亂碼！")
st.markdown("---")

# 自動檢查並從 GitHub 下載中文字型（若本地找不到）
font_path = "NotoSansTC-VariableFont_wght.ttf"
github_font_url = "https://github.com/google/fonts/raw/main/ofl/notosanstc/NotoSansTC-VariableFont_wght.ttf"

if not os.path.exists(font_path):
    try:
        res = requests.get(github_font_url, timeout=10)
        if res.status_code == 200:
            with open(font_path, "wb") as f:
                f.write(res.content)
    except Exception:
        pass

if "articles_preview" not in st.session_state:
    st.session_state.articles_preview = []
if "pdf_data" not in st.session_state:
    st.session_state.pdf_data = None

lang_choice = st.selectbox(
    "🌐 選擇教材文章語言：",
    [
        "繁體中文多元閱讀 (Traditional Chinese)",
        "英文閱讀教材 (English Reading)"
    ]
)

if "繁體中文" in lang_choice:
    category_feeds = {
        "科學新知與自然": "https://pansci.asia/feed",
        "科技與數位趨勢": "https://technews.tw/feed/",
        "世界與社會脈動": "https://feeds.bbci.co.uk/zhongwen/trad/rss.xml"
    }
    default_cats = ["科學新知與自然", "科技與數位趨勢"]
else:
    category_feeds = {
        "Science & Nature (科學與自然)": "https://feeds.bbci.co.uk/news/science_and_environment/rss.xml",
        "Culture & Arts (文化與藝術)": "https://feeds.bbci.co.uk/news/entertainment_and_arts/rss.xml",
        "Technology & AI (科技與AI)": "https://feeds.bbci.co.uk/news/technology/rss.xml",
        "Health & Medicine (健康醫療)": "https://feeds.bbci.co.uk/news/health/rss.xml",
        "World News (世界新聞)": "https://feeds.bbci.co.uk/news/world/rss.xml"
    }
    default_cats = ["Science & Nature (科學與自然)", "Culture & Arts (文化與藝術)"]

selected_categories = st.multiselect(
    "📌 請勾選您想納入教材的多元分類（可複選）：",
    list(category_feeds.keys()),
    default=default_cats
)

article_count = st.slider("📊 目標成功抓取的總文章篇數：", min_value=3, max_value=25, value=6)
custom_book_title = st.text_input("📄 自訂整本 PDF 大標題（選填）：", placeholder="跨領域多元閱讀精選教材")

def fetch_web_content(url):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
    }
    try:
        response = requests.get(url, headers=headers, timeout=5, allow_redirects=True)
        response.raise_for_status()
        response.encoding = response.apparent_encoding
        html_content = response.text
        
        clean_text = trafilatura.extract(html_content, include_comments=False, include_tables=False, include_formatting=True)
        metadata = trafilatura.extract_metadata(html_content)
        article_title = metadata.title if metadata and metadata.title else None
        
        soup = BeautifulSoup(html_content, 'html.parser')
        if not article_title:
            article_title = soup.title.string.strip() if soup.title else "無標題文章"
            
        if not clean_text or len(clean_text) < 150:
            for element in soup(["script", "style", "nav", "header", "footer", "aside", "form"]):
                element.decompose()
            target_tags = soup.find_all('p')
            content_lines = [p.get_text().strip() for p in target_tags if len(p.get_text().strip()) > 30]
            clean_text = "\n".join(content_lines)
            
        if not clean_text or len(clean_text) < 150:
            return None, None, url
            
        return article_title, clean_text, url
    except Exception:
        return None, None, url

if st.button("🚀 步驟一：一鍵快速載入各領域穩定文章", type="primary"):
    if not selected_categories:
        st.warning("⚠️ 請至少勾選一個分類！")
    else:
        valid_articles = []
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        all_tasks = []
        for cat in selected_categories:
            rss_url = category_feeds[cat]
            feed = feedparser.parse(rss_url)
            for entry in feed.entries[:6]:
                all_tasks.append((cat, entry.title, entry.link))
                
        total_tasks = len(all_tasks)
        if total_tasks == 0:
            st.warning("⚠️ 目前頻道無法讀取，請稍後再試。")
        else:
            status_text.text(f"正在從選定的多元分類中高速載入文章...")
            completed = 0
            
            with ThreadPoolExecutor(max_workers=6) as executor:
                future_to_meta = {
                    executor.submit(fetch_web_content, link): (cat, rss_title)
                    for cat, rss_title, link in all_tasks
                }
                
                for future in as_completed(future_to_meta):
                    completed += 1
                    progress_bar.progress(min(completed / total_tasks, 1.0))
                    
                    cat, rss_title = future_to_meta[future]
                    try:
                        title, content, final_url = future.result()
                        if content and len(content) >= 150:
                            if len(valid_articles) < article_count:
                                if not title or title == "無標題文章":
                                    title = rss_title
                                
                                if not any(a['url'] == final_url for a in valid_articles):
                                    valid_articles.append({
                                        "index": len(valid_articles) + 1,
                                        "selected": True,
                                        "category": cat.split(" ")[0],
                                        "url": final_url,
                                        "title": title,
                                        "content": content,
                                        "snippet": content[:150] + "..." if len(content) > 150 else content
                                    })
                    except Exception:
                        continue
            
            progress_bar.progress(1.0)
            status_text.empty()
            progress_bar.empty()
            
            if valid_articles:
                st.session_state.articles_preview = valid_articles
                st.success(f"✅ 成功載入 {len(valid_articles)} 篇多元文章，請於下方檢查與勾選！")
            else:
                st.warning("⚠️ 載入發生阻擋，請重新點擊按鈕嘗試。")

if st.session_state.articles_preview:
    st.markdown("---")
    st.markdown("### 📋 步驟二：檢查內容並勾選您要納入 PDF 的文章")
    
    updated_articles = []
    for art in st.session_state.articles_preview:
        with st.expander(f"【第 {art['index']} 篇】[{art.get('category', '綜合' )}] {art['title']}"):
            is_checked = st.checkbox("勾選此篇納入 PDF", value=art["selected"], key=f"chk_{art['index']}")
            st.markdown(f"**分類領域**：{art.get('category', '綜合')}")
            st.markdown(f"**來源網址**：[{art['url']}]({art['url']})")
            st.markdown(f"**內文預覽**：\n> {art['snippet']}")
            
            updated_articles.append({
                "index": art['index'],
                "selected": is_checked,
                "category": art.get('category', '綜合'),
                "url": art['url'],
                "title": art['title'],
                "content": art['content']
            })
    
    st.markdown("---")
    if st.button("🚀 步驟三：將勾選的文章製作成 PDF 教材", type="secondary"):
        selected_ones = [a for a in updated_articles if a['selected']]
        
        if not selected_ones:
            st.warning("⚠️ 您尚未勾選任何文章！")
        else:
            with st.spinner("📄 正在排版並產生教材 PDF 中..."):
                try:
                    from reportlab.lib.pagesizes import A4
                    from reportlab.pdfgen import canvas
                    from reportlab.pdfbase import pdfmetrics
                    from reportlab.pdfbase.ttfonts import TTFont
                    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak, Table, TableStyle
                    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
                    from reportlab.lib import colors

                    # 強制註冊並使用中文字型
                    font_name = "CustomVariableFont"
                    if os.path.exists(font_path):
                        pdfmetrics.registerFont(TTFont(font_name, font_path))
                    else:
                        st.error(f"❌ 找不到字型檔 {font_path}，無法正確渲染中文！")

                    class TrackedParagraph(Paragraph):
                        def __init__(self, text, style, unit_index=None, tracking_dict=None):
                            super().__init__(text, style)
                            self.unit_index = unit_index
                            self.tracking_dict = tracking_dict

                        def draw(self):
                            if self.unit_index is not None and self.tracking_dict is not None:
                                self.tracking_dict[self.unit_index] = self.canv._pageNumber
                            super().draw()

                    class NumberedCanvas(canvas.Canvas):
                        def __init__(self, *args, **kwargs):
                            super().__init__(*args, **kwargs)
                            self._saved_page_states = []

                        def showPage(self):
                            self._saved_page_states.append(dict(self.__dict__))
                            self._startPage()

                        def save(self):
                            for state in self._saved_page_states:
                                self.__dict__.update(state)
                                self.draw_footer()
                                super().showPage()
                            super().save()

                        def draw_footer(self):
                            self.saveState()
                            self.setFont(font_name, 9)
                            self.setFillColor(colors.HexColor("#495057"))
                            self.drawCentredString(A4[0] / 2, 28, f"{self._pageNumber}")
                            self.restoreState()

                    page_dict = {}
                    buffer = None
                    
                    export_list = []
                    for new_idx, art in enumerate(selected_ones, 1):
                        export_list.append({
                            "index": new_idx,
                            "category": art['category'],
                            "title": art['title'],
                            "url": art['url'],
                            "content": art['content']
                        })

                    for _ in range(2):
                        buffer = io.BytesIO()
                        doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=50, leftMargin=50, topMargin=50, bottomMargin=45)
                        styles = getSampleStyleSheet()
                        
                        # 確保所有建立的樣式都套用中文字型 (fontName=font_name)
                        title_style = ParagraphStyle('T1', parent=styles['Heading1'], fontName=font_name, fontSize=14, leading=18, alignment=1, textColor=colors.HexColor("#0D1B2A"))
                        body_style = ParagraphStyle('B1', parent=styles['Normal'], fontName=font_name, fontSize=10, leading=16, textColor=colors.HexColor("#212529"))
                        toc_l = ParagraphStyle('TL', parent=styles['Normal'], fontName=font_name, fontSize=10, leading=18, textColor=colors.HexColor("#1B263B"))
                        toc_r = ParagraphStyle('TR', parent=styles['Normal'], fontName=font_name, fontSize=10, leading=18, alignment=2, textColor=colors.HexColor("#1B263B"))
                        sub_style = ParagraphStyle('Sub', parent=body_style, fontSize=8, textColor=colors.gray, fontName=font_name)

                        story = []
                        book_title = custom_book_title if custom_book_title else "跨領域多元閱讀精選教材"
                        
                        story.append(Paragraph(f"【 {book_title} - 目錄 】", title_style))
                        story.append(Spacer(1, 15))
                        
                        toc_data = []
                        for art in export_list:
                            pg = page_dict.get(art['index'], 2)
                            clean_t = f"[{art['category']}] {art['title']}"
                            clean_t = clean_t[:35] + "..." if len(clean_t) > 35 else clean_t
                            toc_data.append([Paragraph(f"第 {art['index']} 篇：{clean_t}", toc_l), Paragraph(f"第 {pg} 頁", toc_r)])
                        
                        if toc_data:
                            t = Table(toc_data, colWidths=[415, 80])
                            t.setStyle(TableStyle([('VALIGN', (0,0), (-1,-1), 'MIDDLE'), ('BOTTOMPADDING', (0,0), (-1,-1), 6)]))
                            story.append(t)
                        story.append(PageBreak())

                        for art in export_list:
                            story.append(TrackedParagraph(f"【 第 {art['index']} 篇 】 {art['title']}", title_style, unit_index=art['index'], tracking_dict=page_dict))
                            story.append(Spacer(1, 4))
                            story.append(Paragraph(f"領域：{art['category']} | 來源：{art['url']}", sub_style))
                            story.append(Spacer(1, 12))
                            
                            for p in art['content'].split('\n'):
                                if p.strip():
                                    story.append(Paragraph(p.strip(), body_style))
                                    story.append(Spacer(1, 6))

                            if art['index'] < len(export_list):
                                story.append(PageBreak())

                        doc.build(story, canvasmaker=NumberedCanvas)
                    
                    buffer.seek(0)
                    st.session_state.pdf_data = buffer
                    st.success("🎉 教材 PDF 檔案製作成功！")

                except Exception as e:
                    st.error(f"❌ 產生 PDF 發生錯誤：{e}")

if st.session_state.pdf_data:
    st.markdown("---")
    st.download_button(
        label="📥 下載多元閱讀教材 PDF",
        data=st.session_state.pdf_data,
        file_name="Multi_Disciplinary_Reading_教材.pdf",
        mime="application/pdf",
        key="btn_download_final"
    )