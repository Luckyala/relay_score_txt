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
    try:
        # 입력값 검증
        if not name or not isinstance(name, str):
            return ""
        
        # 번호와 괄호 제거 (예: "4) ", "8) ")
        cleaned_name = re.sub(r'^\d+\)\s*', '', name.strip())
        
        # 공백과 슬래시로 분할
        parts = re.split(r"[\s/]", cleaned_name)
        parts = [p.strip() for p in parts if p.strip()]
        
        if not parts:
            return cleaned_name.strip() if cleaned_name.strip() else name.strip()
        
        # 팀명이나 불필요한 단어 필터링
        blacklist = {"하고랩스", "사부작사부작", "으랏차", "BGO", "and"}
        
        # 조 번호 제거 및 blacklist 필터링
        filtered_parts = []
        for p in parts:
            try:
                if not re.match(r"^\d+조$", p) and p not in blacklist:
                    filtered_parts.append(p)
            except:
                continue
        
        if not filtered_parts:
            return name.strip()
        
        # 1. 한국어 이름 우선 검색 (2-4글자)
        korean_parts = []
        for p in filtered_parts:
            try:
                if re.match(r"^[가-힣]{2,4}$", p):
                    korean_parts.append(p)
            except:
                continue
        
        if korean_parts:
            return max(korean_parts, key=len)
        
        # 2. 영어 이름 검색 (2글자 이상)
        english_parts = []
        for p in filtered_parts:
            try:
                if re.match(r"^[a-zA-Z]{2,}$", p):
                    english_parts.append(p)
            except:
                continue
        
        if english_parts:
            return english_parts[-1]
        
        # 3. ID 형식 검색 (한글+영문+숫자+언더스코어 4글자 이상)
        id_parts = []
        for p in filtered_parts:
            try:
                if re.match(r"^[가-힣a-zA-Z0-9_]{4,}$", p):
                    id_parts.append(p)
            except:
                continue
        
        if id_parts:
            return id_parts[-1]
        
        # 4. 모든 조건에 맞지 않으면 남은 부분을 정렬해서 반환
        if filtered_parts:
            return " ".join(sorted(filtered_parts))
        else:
            return name.strip()
            
    except Exception as e:
        # 에러 발생시 원본 반환
        return name.strip() if isinstance(name, str) else str(name)

def extract_date_from_filename(filename):
    try:
        if not filename:
            return None
            
        match = re.search(r"(\d{4}[.-]?\d{2}[.-]?\d{2}|\d{1,2}월\s*\d{1,2}일|\d{4})", filename)
        if match:
            raw_date = match.group(1)
            try:
                if "월" in raw_date:
                    m = re.search(r"(\d{1,2})월\s*(\d{1,2})일", raw_date)
                    if m:
                        return datetime.strptime(f"2024-{int(m.group(1)):02}-{int(m.group(2)):02}", "%Y-%m-%d").date()
                elif re.match(r"^\d{4}$", raw_date):
                    return datetime.strptime(f"2024-{raw_date[:2]}-{raw_date[2:]}", "%Y-%m-%d").date()
                else:
                    cleaned_date = raw_date.replace('.', '-').replace('_', '-')
                    return datetime.strptime(cleaned_date, "%Y-%m-%d").date()
            except ValueError:
                return None
        return None
    except Exception:
        return None

if uploaded_files:
    content_records = []
    all_dates = set()

    for file in uploaded_files:
        try:
            date = extract_date_from_filename(file.name)
            if not date:
                st.warning(f"⚠️ 날짜 인식 실패: {file.name}")
                continue
            all_dates.add(date)

            # 파일 읽기 개선
            try:
                text_content = file.read().decode('utf-8')
                text = text_content.splitlines()
            except UnicodeDecodeError:
                try:
                    file.seek(0)  # 파일 포인터 리셋
                    text_content = file.read().decode('cp949')
                    text = text_content.splitlines()
                except:
                    st.error(f"파일 읽기 실패: {file.name}")
                    continue

            current_name = None
            current_content = []
            
            for line in text:
                line = line.strip()
                if not line:
                    continue
                    
                match = pattern.match(line)
                if match:
                    # 이전 내용 저장
                    if current_name and current_content:
                        content_records.append({
                            "이름": current_name,
                            "날짜": date,
                            "내용": " ".join(current_content).strip()
                        })
                    
                    # 새로운 이름 처리
                    raw_name = match.group(2)
                    current_name = normalize_name_to_core(raw_name)
                    current_content = []
                elif current_name:
                    current_content.append(line)

            # 마지막 내용 저장
            if current_name and current_content:
                content_records.append({
                    "이름": current_name,
                    "날짜": date,
                    "내용": " ".join(current_content).strip()
                })
                
        except Exception as e:
            st.error(f"파일 처리 중 오류 발생: {file.name} - {str(e)}")
            continue

    # 데이터프레임 생성 및 표시
    if content_records:
        try:
            df_content = pd.DataFrame(content_records)
            
            st.subheader("📊 이름별 날짜별 작성 내용")
            
            # 피벗 테이블 생성 (중복 처리 개선)
            df_pivot = df_content.groupby(['이름', '날짜'])['내용'].apply(
                lambda x: ' | '.join(x) if len(x) > 1 else x.iloc[0]
            ).unstack(fill_value='')
            
            # 날짜 순서로 정렬
            df_pivot = df_pivot.reindex(sorted(df_pivot.columns), axis=1)
            st.dataframe(df_pivot)

            # 참여 횟수 + 총점 계산
            df_count = (df_pivot != '').sum(axis=1).reset_index()
            df_count.columns = ['이름', '참여 횟수']
            df_count['총점'] = df_count['참여 횟수'] * 1

            st.subheader("🏅 이름별 참여 횟수 및 총점")
            st.dataframe(df_count.sort_values('참여 횟수', ascending=False))

            # 다운로드 버튼
            st.download_button(
                "📥 작성 내용 (CSV)", 
                df_pivot.to_csv(encoding='utf-8-sig'), 
                "이름별_날짜별_내용.csv", 
                "text/csv"
            )
            st.download_button(
                "📥 참여 횟수 및 총점 (CSV)", 
                df_count.to_csv(index=False, encoding='utf-8-sig'), 
                "참여횟수_총점.csv", 
                "text/csv"
            )

            # Excel 다운로드
            try:
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
            except Exception as e:
                st.error(f"Excel 파일 생성 중 오류: {str(e)}")
                
        except Exception as e:
            st.error(f"데이터 처리 중 오류 발생: {str(e)}")
    else:
        st.warning("처리된 데이터가 없습니다. 파일 형식이나 내용을 확인해주세요.")
else:
    st.info("텍스트 파일을 업로드해주세요.")
    
