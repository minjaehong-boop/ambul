"""지침 파일 직접 접근 관리자 (Pure Protocol Mode).

벡터 DB 없이, 설정된 디렉터리의 .md 지침 파일을 스캔해 파일명 키워드로 제공한다.
"""

import os
import glob

from . import config


class DataManager:
    def __init__(self, protocol_dir=None):
        print("\n[Server] DataManager 초기화...")
        self.protocol_dir = protocol_dir or config.PROTOCOL_DIR
        self.file_map = {}
        self._scan_filesystem()

    def _scan_filesystem(self):
        if not os.path.exists(self.protocol_dir):
            print(f"[Warning] 지정된 경로를 찾을 수 없음: {self.protocol_dir}")
            print("          config.PROTOCOL_DIR / PROTOCOL_DIR 환경변수를 확인하세요.")
        else:
            print(f"[Server] 프로토콜 파일 스캔 중... (Target: {self.protocol_dir})")

        files = glob.glob(os.path.join(self.protocol_dir, "**", "*.md"), recursive=True)
        for file_path in files:
            filename = os.path.basename(file_path)
            clean_name = os.path.splitext(filename)[0]
            # 파일명, 확장자 제거명, 공백 제거명 세 가지 키로 인덱싱 (부분 매칭 보강)
            self.file_map[filename] = file_path
            self.file_map[clean_name] = file_path
            self.file_map[clean_name.replace(" ", "")] = file_path

        print(f"[Server] 총 {len(files)}개의 프로토콜 파일이 로드되었습니다.")

    def read_specific_files(self, target_names):
        """키워드 리스트 → 매칭된 지침 파일 전문 리스트."""
        docs = []
        for name in target_names:
            path = self.file_map.get(name)
            if not path:
                name_clean = name.replace(" ", "")
                for key, val in self.file_map.items():
                    if name_clean in key.replace(" ", ""):
                        path = val
                        break

            if path and os.path.exists(path):
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        content = f.read()
                    docs.append({
                        "source": os.path.basename(path),
                        "page": "Full Document",
                        "content": content,
                    })
                except Exception as e:
                    print(f"[Error] 파일 읽기 실패 ({path}): {e}")
            else:
                print(f"[Warning] 요청한 파일을 찾을 수 없음: {name}")

        return docs
