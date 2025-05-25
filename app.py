import streamlit as st
import re
import pandas as pd
from io import BytesIO
from collections import defaultdict, Counter
from datetime import datetime

st.title("패턴 기반 이름별 날짜별 작성 내용 + 참여 횟수 + 총점 분석기")
st.write("번호 뒤의 모든 텍스트를 추출하고 겹치는 패턴으로 참여자를 식별합니다.")

uploaded_files = st.file_uploader("📂 텍스트 파일들을 업로드하세요", type=["txt"], accept_multiple_files=True)

# 단순한 패턴: 번호) 뒤의 모든 내용
pattern = re.compile(r"^(\d+)\)\s*(.*)")

def extract_all_name_parts(text_list):
    """모든 번호 뒤의 텍스트에서 이름 후보들을 추출"""
    all_parts = []
    
    for text in text_list:
        # 공백, 슬래시, 하이픈으로 분할
        parts = re.split(r"[\s/\-]+", text.strip())
        parts = [p.strip() for p in parts if p.strip()]
        
        # 각 파트를 정리
        cleaned_parts = []
        for p in parts:
            # 조 번호 제거
            if re.match(r"^\d+조$", p):
                continue
            # 너무 짧은 것 제거 (1글자)
            if len(p) < 2:
                continue
            # 숫자만 있는 것 제거
            if p.isdigit():
                continue
            cleaned_parts.append(p)
        
        all_parts.extend(cleaned_parts)
    
    return all_parts

def find_common_patterns(all_parts):
    """자주 등장하는 패턴을 찾아서 참여자 식별"""
    # 빈도수 계산
    part_counter = Counter(all_parts)
    
    # 2번 이상 등장하는 것들만 후보로
    candidates = {part: count for part, count in part_counter.items() if count >= 2}
    
    # 한국어 이름 우선순위
    korean_names = {part: count for part, count in candidates.items() 
                   if re.match(r"^[가-힣]{2,4}$", part)}
    
    # 영어 이름/별명
    english_names = {part: count for part, count in candidates.items() 
                    if re.match(r"^[a-zA-Z]{2,}$", part)}
    
    # 혼합 ID (한글+영문+숫자)
    mixed_ids = {part: count for part, count in candidates.items() 
                if re.match(r"^[가-힣a-zA-Z0-9_]{3,}$", part) and part not in korean_names and part not in english_names}
    
    return {
        'korean': korean_names,
        'english': english_names, 
        'mixed': mixed_ids,
        'all_candidates': candidates
    }

def smart_name_matching(raw_name, name_patterns):
    """패턴을 기반으로 실제 참여자 이름 찾기"""
    # 원본에서 파트 추출
    parts = re.split(r"[\s/\-]+", raw_name.strip())
    parts = [p.strip() for p in parts if p.strip() and len(p) >= 2 and not p.isdigit() and not re.match(r"^\d+조$", p)]
    
    # 알려진 패턴과 매칭
    matched_names = []
    
    for part in parts:
        # 한국어 이름 우선
        if part in name_patterns['korean']:
            matched_names.append((part, name_patterns['korean'][part], 'korean'))
        elif part in name_patterns['english']:
            matched_names.append((part, name_patterns['english'][part], 'english'))
        elif part in name_patterns['mixed']:
            matched_names.append((part, name_patterns['mixed'][part], 'mixed'))
    
    if matched_names:
        # 가장 빈도가 높고 한국어 이름을 우선으로
        matched_names.sort(key=lambda x: (x[2] == 'korean', x[1]), reverse=True)
        return matched_names[0][0]
    
    # 매칭되는 패턴이 없으면 가장 적절한 부분 선택
    korean_parts = [p for p in parts if re.match(r"^[가-힣]{2,4}$", p)]
    if korean_parts:
        return max(korean_parts, key=len)
    
    english_parts = [p for p in parts if re.match(r"^[a-zA-Z]{2,}$", p)]
    if english_parts:
        return english_parts[-1]
    
    return parts[0] if parts else raw_name

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
    content_records = []
    all_dates = set()

    st.info("1단계: 모든 파일에서 이름 패턴 수집 중...")
    
    for file in uploaded_files:
        try:
            date = extract_date_from_filename(file.name)
            if not date:
                st.warning(f"⚠️ 날짜 인식 실패: {file.name}")
                continue
            all_dates.add(date)

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
            for line in text:
                line = line.strip()
                if not line:
                    continue
                    
                match = pattern.match(line)
                if match:
                    raw_name = match.group(2).strip()
                    if raw_name:
                        all_raw_names.append(raw_name)
                        
        except Exception as e:
            st.error(f"파일 처리 중 오류 발생: {file.name} - {str(e)}")
            continue

    # 2단계: 패턴 분석
    if all_raw_names:
        st.info("2단계: 이름 패턴 분석 중...")
        
        all_parts = extract_all_name_parts(all_raw_names)
        name_patterns = find_common_patterns(all_parts)
        
        # 디버깅: 원시 데이터 표시
        with st.expander("🔍 디버깅: 원시 데이터 확인"):
            st.write("**수집된 원시 이름들 (처음 20개):**")
            for i, raw_name in enumerate(all_raw_names[:20]):
                st.write(f"{i+1}. '{raw_name}'")
            
            if len(all_raw_names) > 20:
                st.write(f"... 총 {len(all_raw_names)}개")
            
            st.write("**분할된 모든 파트들 (빈도순 상위 30개):**")
            part_counter = Counter(all_parts)
            for part, count in part_counter.most_common(30):
                st.write(f"- '{part}': {count}회")
        
        # 패턴 분석 결과 표시
        st.subheader("🔍 발견된 이름 패턴 (2회 이상)")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.write("**한국어 이름:**")
            if name_patterns['korean']:
                for name, count in sorted(name_patterns['korean'].items(), key=lambda x: x[1], reverse=True):
                    st.write(f"- {name} ({count}회)")
            else:
                st.write("발견된 한국어 이름 없음")
        
        with col2:
            st.write("**영어 이름/별명:**")
            if name_patterns['english']:
                for name, count in sorted(name_patterns['english'].items(), key=lambda x: x[1], reverse=True):
                    st.write(f"- {name} ({count}회)")
            else:
                st.write("발견된 영어 이름 없음")
        
        with col3:
            st.write("**기타 ID:**")
            if name_patterns['mixed']:
                for name, count in sorted(name_patterns['mixed'].items(), key=lambda x: x[1], reverse=True):
                    st.write(f"- {name} ({count}회)")
            else:
                st.write("발견된 기타 ID 없음")
        
        # 임계값 조정 옵션
        st.subheader("⚙️ 설정 조정")
        min_frequency = st.slider("최소 등장 횟수 (낮출수록 더 많은 이름 인식)", 1, 5, 2)
        
        if min_frequency != 2:
            # 임계값 변경시 다시 계산
            candidates = {part: count for part, count in part_counter.items() if count >= min_frequency}
            
            korean_names = {part: count for part, count in candidates.items() 
                           if re.match(r"^[가-힣]{2,4}$", part)}
            english_names = {part: count for part, count in candidates.items() 
                            if re.match(r"^[a-zA-Z]{2,}$", part)}
            mixed_ids = {part: count for part, count in candidates.items() 
                        if re.match(r"^[가-힣a-zA-Z0-9_]{3,}$", part) and part not in korean_names and part not in english_names}
            
            name_patterns = {
                'korean': korean_names,
                'english': english_names, 
                'mixed': mixed_ids,
                'all_candidates': candidates
            }
            
            st.write(f"**조정된 패턴 ({min_frequency}회 이상):**")
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.write("**한국어 이름:**")
                for name, count in sorted(korean_names.items(), key=lambda x: x[1], reverse=True):
                    st.write(f"- {name} ({count}회)")
            
            with col2:
                st.write("**영어 이름/별명:**")
                for name, count in sorted(english_names.items(), key=lambda x: x[1], reverse=True):
                    st.write(f"- {name} ({count}회)")
            
            with col3:
                st.write("**기타 ID:**")
                for name, count in sorted(mixed_ids.items(), key=lambda x: x[1], reverse=True):
                    st.write(f"- {name} ({count}회)")

        # 3단계: 실제 데이터 처리
        st.info("3단계: 데이터 처리 및 매칭 중...")
        
        for file in uploaded_files:
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
                
                # 매칭 과정 디버깅
                matching_debug = []
                
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
                        
                        # 새로운 이름 처리 (패턴 기반 매칭)
                        raw_name = match.group(2).strip()
                        matched_name = smart_name_matching(raw_name, name_patterns)
                        
                        # 디버깅 정보 수집
                        matching_debug.append({
                            'raw': raw_name,
                            'matched': matched_name,
                            'date': date
                        })
                        
                        current_name = matched_name
                        current_content = []
                    elif current_name:
                        current_content.append(line)

                # 매칭 결과 저장 (나중에 표시용)
                if 'all_matching_debug' not in st.session_state:
                    st.session_state.all_matching_debug = []
                st.session_state.all_matching_debug.extend(matching_debug)

                # 마지막 내용 저장
                if current_name and current_content:
                    content_records.append({
                        "이름": current_name,
                        "날짜": date,
                        "내용": " ".join(current_content).strip()
                    })
                    
            except Exception as e:
                st.error(f"파일 재처리 중 오류 발생: {file.name} - {str(e)}")
                continue

        # 결과 표시
        if content_records:
            try:
                # 매칭 결과 디버깅 표시
                if 'all_matching_debug' in st.session_state and st.session_state.all_matching_debug:
                    with st.expander("🔍 디버깅: 이름 매칭 결과"):
                        st.write("**원본 → 매칭된 이름:**")
                        matching_df = pd.DataFrame(st.session_state.all_matching_debug)
                        
                        # 고유한 매칭만 표시
                        unique_matching = matching_df.drop_duplicates(['raw', 'matched'])
                        
                        for _, row in unique_matching.iterrows():
                            if row['raw'] != row['matched']:
                                st.write(f"'{row['raw']}' → **{row['matched']}**")
                            else:
                                st.write(f"'{row['raw']}' → {row['matched']} (변경없음)")
                
                df_content = pd.DataFrame(content_records)
                
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
                        mime="application/vnd.openxmlformats-officedocument.spreadsheettml.sheet"
                    )
                except Exception as e:
                    st.error(f"Excel 파일 생성 중 오류: {str(e)}")
                    
            except Exception as e:
                st.error(f"데이터 처리 중 오류 발생: {str(e)}")
        else:
            st.warning("처리된 데이터가 없습니다. 파일 형식이나 내용을 확인해주세요.")
    else:
        st.warning("이름 패턴을 찾을 수 없습니다. 파일 내용을 확인해주세요.")
else:
    st.info("텍스트 파일을 업로드해주세요.")
