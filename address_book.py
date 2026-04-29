import sqlite3
import pandas as pd # type: ignore
import os

DB_PATH = "auto_sms.db"

class AddressBookManager:
    def __init__(self, db_path=DB_PATH):
        self.db_path = db_path

    def get_all_contacts(self):
        conn = sqlite3.connect(self.db_path)
        df = pd.read_sql_query("SELECT * FROM contacts ORDER BY name ASC", conn)
        conn.close()
        return df

    def add_contact(self, name, phone, category="", memo=""):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        try:
            cursor.execute("INSERT INTO contacts (name, phone, category, memo) VALUES (?, ?, ?, ?)", 
                           (name, phone, category, memo))
            conn.commit()
            return True, "성공"
        except sqlite3.IntegrityError:
            return False, "이미 존재하는 전화번호입니다."
        finally:
            conn.close()

    def update_contact(self, contact_id, name, phone, category="", memo=""):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("UPDATE contacts SET name=?, phone=?, category=?, memo=? WHERE id=?", 
                       (name, phone, category, memo, contact_id))
        conn.commit()
        conn.close()

    def delete_contact(self, contact_id):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM contacts WHERE id=?", (contact_id,))
        conn.commit()
        conn.close()

    def delete_contacts_by_phone(self, phones):
        if not phones: return
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        placeholders = ', '.join(['?'] * len(phones))
        cursor.execute(f"DELETE FROM contacts WHERE phone IN ({placeholders})", phones)
        conn.commit()
        conn.close()

    def clear_all_contacts(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM contacts")
        conn.commit()
        conn.close()

    def import_from_excel(self, file_path):
        """
        엑셀 파일(xlsx, csv)을 읽어 DB에 저장합니다.
        엑셀 헤더는 '이름', '전화번호', '그룹', '메모'를 기본으로 삼습니다.
        """
        try:
            if file_path.endswith('.csv'):
                df = pd.read_csv(file_path)
            else:
                df = pd.read_excel(file_path)
            
            # 컬럼 매핑 (추측 및 확장)
            mapping = {
                '이름': 'name', 'name': 'name', 'Name': 'name',
                '전화번호': 'phone', 'phone': 'phone', 'Phone': 'phone', '연락처': 'phone',
                '그룹': 'category', 'category': 'category', 'Category': 'category', '카테고리': 'category',
                '메모': 'memo', 'memo': 'memo', 'Memo': 'memo'
            }
            # 실제 파일 컬럼 중 매핑 가능한 것들만 추출하여 이름 변경
            available_columns = {col: mapping[col] for col in df.columns if col in mapping}
            df = df.rename(columns=available_columns)
            
            conn = sqlite3.connect(self.db_path)
            added_count = 0
            for _, row in df.iterrows():
                try:
                    p = str(row.get('phone', '')).strip()
                    if not p or p == 'nan': continue
                    
                    conn.execute("INSERT INTO contacts (name, phone, category, memo) VALUES (?, ?, ?, ?)", 
                                 (row.get('name', '이름없음'), p, row.get('category', ''), row.get('memo', '')))
                    added_count += 1
                except:
                    continue # 중복 등은 무시
            conn.commit()
            conn.close()
            return True, f"{added_count}개의 연락처를 성공적으로 불러왔습니다."
        except Exception as e:
            return False, f"오류 발생: {str(e)}"

    def export_to_excel(self, file_path):
        """
        주소록 전체를 엑셀 파일로 저장합니다.
        """
        try:
            df = self.get_all_contacts()
            df.to_excel(file_path, index=False)
            return True, "엑셀 저장을 완료했습니다."
        except Exception as e:
            return False, str(e)

if __name__ == "__main__":
    mgr = AddressBookManager()
    mgr.add_contact("홍길동", "01011112222", "학생", "우수고객")
    print(mgr.get_all_contacts())
