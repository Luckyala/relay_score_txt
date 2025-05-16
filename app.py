import streamlit as st
import re
import pandas as pd
from io import BytesIO
from collections import defaultdict
from datetime import datetime

st.title("이름별 날짜별 작성 내용 + 참여 횟수 + 총점 분석기")
st.write("텍스트 파일에서 이름, 날짜, 내용을 추출하고 참여 횟수 및 총점까지 계산합니다.")

uploaded_files = st.file_uploader("📂 텍스트 파일들을 업로드하세요", type=["txt"], accept_multiple_files=True)

pattern = re.compile(r"^(\d+)\)\s*(?:(?:\d+조|[가-힣]+조)[\s/]*)?([\w가-힣/_]+(?:[\s/][\w가-힣/_]+)*)")

def normalize_name_to_core(name):
    parts = re.split(r"[\s/]", name.strip())
    parts = [p for p in parts if p]
    blacklist = {"하고랩스", "사부작사부작", "으랏차", "인스피레이션", "BGO"}
    parts = [p for p in parts if not re.fullmatch(r"\d+조", p) and p not in blacklist]
    korean_parts = [p for p in parts if re.fullmatch(r"[가-힣]{2,3}", p)]
    if korean_parts:
        return max(korean_parts, key=len)
    id_parts = [p for p in parts if re.fullmatch(r"[가-힣a-zA-Z0-9_]{4,}", p)]
    if id_parts:
        return id_parts[-1]
    return " ".join(sorted(parts))

def extract_date_from_filename(filename):
    match = re.search(r"(\d{4}[.-]?\d{2}[.-]?\d{2}|\d{1,2}월\s*\d{1,2}일|\d{4})", filename)
    if match:
        raw_date = match.group(1)
        try:
            if "월" in raw_date:
                m = re.search(r"(\d{1,2})월\s*(\d{1,2})일", raw_date)
                return datetime.strptime(f"2024-{int(m.group(1)):02}-{int(m.group(2)):02}", "%Y-%m-%d").date()
            elif re.fullmatch(r"\d{4}", raw_date):
                return datetime.strptime(f"2024-{raw_date[:2]}-{raw_date[2:]}", "%Y-%m-%d").date()
            else:
                return datetime.strptime(raw_date.replace('.', '-'), "%Y-%m-%d").date()
        except:
            return None
    return None

if uploaded_files:
    content_records = []
    all_dates = set()

    for file in uploaded_files:
        date = extract_date_from_filename(file.name)
        if not date:
            st.error(f"⚠️ 날짜 인식 실패: {file.name}")
            continue
        all_dates.add(date)

        text = file.read().decode('utf-8').splitlines()
        current_name = None
        current_content = []
        for line in text:
            line = line.strip()
            if not line:
                continue
            match = pattern.match(line)
            if match:
                if current_name and current_content:
                    content_records.append({
                        "이름": current_name,
                        "날짜": date,
                        "내용": " ".join(current_content).strip()
                    })
                raw_name = match.group(2)
                current_name = normalize_name_to_core(raw_name)
                current_content = []
            elif current_name:
                current_content.append(line)

        if current_name and current_content:
            content_records.append({
                "이름": current_name,
                "날짜": date,
                "내용": " ".join(current_content).strip()
            })

    df_content = pd.DataFrame(content_records)

    st.subheader("📊 이름별 날짜별 작성 내용")
    if not df_content.empty:
        df_pivot = df_content.pivot(index='이름', columns='날짜', values='내용')
        df_pivot = df_pivot.sort_index(axis=1)
        st.dataframe(df_pivot)

        # 참여 횟수 + 총점
        df_count = df_pivot.notna().sum(axis=1).reset_index()
        df_count.columns = ['이름', '참여 횟수']
        df_count['총점'] = df_count['참여 횟수'] * 1

        st.subheader("🏅 이름별 참여 횟수 및 총점")
        st.dataframe(df_count)

        st.download_button("📥 작성 내용 (CSV)", df_pivot.to_csv(), "이름별_날짜별_내용.csv", "text/csv")
        st.download_button("📥 참여 횟수 및 총점 (CSV)", df_count.to_csv(index=False), "참여횟수_총점.csv", "text/csv")

        buffer = BytesIO()
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
            df_pivot.to_excel(writer, sheet_name="작성내용", index=True)
            df_count.to_excel(writer, sheet_name="참여횟수_총점", index=False)
        buffer.seek(0)

        st.download_button(
            label="📥 전체 다운로드 (Excel)",
            data=buffer,
            file_name="참여내용_및_총점.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
