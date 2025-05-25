import streamlit as st
import re
import pandas as pd
from io import BytesIO
from collections import defaultdict, Counter
from datetime import datetime

st.title("수동 매핑 이름별 날짜별 작성 내용 + 참여 횟수 + 총점 분석기")
st.write("모든 번호 뒤의 텍스트를 추출하고 사용자가 직접 참여자로 매핑합니다.")

uploaded_files = st.file_uploader("📂 텍스트 파일들을 업로드하세요", type=["txt"], accept_multiple_files=True)

# 단순한 패턴: 번호) 뒤의 모든 내용
pattern = re.compile(r"^(\d+)\)\s*(.*)")

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
    # 1단계: 모든 파일에서 원시 이름 데이터 수집
    all_raw_names = []
    raw_name_details = []  # 파일명과 함께 저장
    
    st.info("1단계: 모든 파일에서 이름 수집 중...")
    
    for file in uploaded_files:
        try:
            date = extract_date_from_filename(file.name)
            if not date:
                st.warning(f"⚠️ 날짜 인식 실패: {file.name}")
                continue

            # 파일 읽기
            try:
                text_content = file.read().decode('utf-8')
                text = text_content.splitlines()
            except UnicodeDecodeError:
                try:
                    file.seek(0)
                    text_content = file.read().decode('cp949')
                    text = text_content.splitlines()
                except:
                    st.error(f"파일 읽기 실패: {file.name}")
                    continue

            # 원시 이름 수집
            for line_num, line in enumerate(text, 1):
                line = line.strip()
                if not line:
                    continue
                    
                match = pattern.match(line)
                if match:
                    raw_name = match.group(2).strip()
                    if raw_name:
                        all_raw_names.append(raw_name)
                        raw_name_details.append({
                            'raw_name': raw_name,
                            'file': file.name,
                            'date': date,
                            'line_num': line_num
                        })
                        
        except Exception as e:
            st.error(f"파일 처리 중 오류 발생: {file.name} - {str(e)}")
            continue

    # 2단계: 고유한 원시 이름들 표시 및 매핑 설정
    if all_raw_names:
        st.success(f"총 {len(all_raw_names)}개의 이름 텍스트를 발견했습니다!")
        
        # 고유한 원시 이름들과 빈도
        raw_name_counter = Counter(all_raw_names)
        unique_raw_names = list(raw_name_counter.keys())
        
        st.subheader("📝 이름 매핑 설정")
        st.write("아래에서 각 원시 텍스트를 어떤 참여자 이름으로 매핑할지 설정하세요. 같은 사람이면 같은 이름을 입력하세요.")
        
        # 자동 제안 기능
        def suggest_name(raw_name):
            """간단한 이름 제안 로직"""
            # 번호와 조 제거
            cleaned = re.sub(r'^\d+\)\s*', '', raw_name)
            parts = re.split(r'[\s/\-]+', cleaned)
            parts = [p.strip() for p in parts if p.strip() and not re.match(r'^\d+조$', p)]
            
            # 한국어 이름 찾기
            korean_names = [p for p in parts if re.match(r'^[가-힣]{2,4}$', p)]
            if korean_names:
                return max(korean_names, key=len)
            
            # 영어 이름 찾기
            english_names = [p for p in parts if re.match(r'^[a-zA-Z]{2,}$', p)]
            if english_names:
                return english_names[-1]
            
            # 기타
            if parts:
                return parts[0]
            return raw_name
        
        # 매핑 딕셔너리 저장용
        if 'name_mapping' not in st.session_state:
            st.session_state.name_mapping = {}
            # 초기값으로 자동 제안 설정
            for raw_name in unique_raw_names:
                st.session_state.name_mapping[raw_name] = suggest_name(raw_name)
        
        # 표시 방식 선택
        display_mode = st.radio(
            "표시 방식 선택:",
            ["빈도순 정렬", "알파벳순 정렬", "파일별 그룹화"],
            horizontal=True
        )
        
        if display_mode == "빈도순 정렬":
            sorted_names = sorted(unique_raw_names, key=lambda x: raw_name_counter[x], reverse=True)
        elif display_mode == "알파벳순 정렬":
            sorted_names = sorted(unique_raw_names)
        else:  # 파일별 그룹화
            sorted_names = unique_raw_names
        
        # 매핑 인터페이스
        st.write("---")
        
        # 일괄 매핑 도구
        col1, col2 = st.columns(2)
        with col1:
            if st.button("🔄 자동 제안으로 초기화"):
                for raw_name in unique_raw_names:
                    st.session_state.name_mapping[raw_name] = suggest_name(raw_name)
                st.experimental_rerun()
        
        with col2:
            # 공통 참여자 목록 (이미 매핑된 이름들)
            existing_names = list(set(st.session_state.name_mapping.values()))
            if existing_names:
                st.write(f"**기존 참여자들:** {', '.join(existing_names)}")
        
        # 개별 매핑 설정
        for i, raw_name in enumerate(sorted_names):
            count = raw_name_counter[raw_name]
            
            col1, col2, col3 = st.columns([3, 2, 1])
            
            with col1:
                st.write(f"**'{raw_name}'**")
            
            with col2:
                # 텍스트 입력으로 매핑 설정
                mapped_name = st.text_input(
                    f"참여자 이름",
                    value=st.session_state.name_mapping.get(raw_name, suggest_name(raw_name)),
                    key=f"mapping_{i}",
                    placeholder="참여자 실명 입력"
                )
                st.session_state.name_mapping[raw_name] = mapped_name
            
            with col3:
                st.write(f"({count}회)")
            
            # 상세 정보 표시
            if display_mode == "파일별 그룹화":
                details = [d for d in raw_name_details if d['raw_name'] == raw_name]
                file_info = {}
                for detail in details:
                    if detail['file'] not in file_info:
                        file_info[detail['file']] = 0
                    file_info[detail['file']] += 1
                
                file_summary = ", ".join([f"{file}: {count}회" for file, count in file_info.items()])
                st.caption(f"📁 {file_summary}")
        
        # 매핑 요약
        st.subheader("📊 매핑 요약")
        mapping_summary = defaultdict(list)
        for raw_name, mapped_name in st.session_state.name_mapping.items():
            mapping_summary[mapped_name].append(raw_name)
        
        for mapped_name, raw_names in mapping_summary.items():
            if mapped_name.strip():  # 빈 이름 제외
                st.write(f"**{mapped_name}**: {', '.join(raw_names)}")
        
        # 3단계: 실제 데이터 처리
        if st.button("✅ 매핑 완료 - 데이터 처리 시작"):
            content_records = []
            
            st.info("데이터 처리 중...")
            progress_bar = st.progress(0)
            
            for file_idx, file in enumerate(uploaded_files):
                try:
                    date = extract_date_from_filename(file.name)
                    if not date:
                        continue

                    # 파일 읽기
                    try:
                        file.seek(0)  # 파일 포인터 리셋
                        text_content = file.read().decode('utf-8')
                        text = text_content.splitlines()
                    except UnicodeDecodeError:
                        try:
                            file.seek(0)
                            text_content = file.read().decode('cp949')
                            text = text_content.splitlines()
                        except:
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
                            
                            # 새로운 이름 처리 (매핑 사용)
                            raw_name = match.group(2).strip()
                            current_name = st.session_state.name_mapping.get(raw_name, raw_name)
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
                    
                    progress_bar.progress((file_idx + 1) / len(uploaded_files))
                        
                except Exception as e:
                    st.error(f"파일 처리 중 오류 발생: {file.name} - {str(e)}")
                    continue

            # 결과 표시
            if content_records:
                try:
                    df_content = pd.DataFrame(content_records)
                    
                    # 빈 이름 제거
                    df_content = df_content[df_content['이름'].str.strip() != '']
                    
                    st.subheader("📊 이름별 날짜별 작성 내용")
                    
                    # 피벗 테이블 생성
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
                st.warning("처리된 데이터가 없습니다.")
    else:
        st.warning("이름을 찾을 수 없습니다. 파일 내용을 확인해주세요.")
else:
    st.info("텍스트 파일을 업로드해주세요.")
