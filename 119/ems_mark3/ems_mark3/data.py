"""Direct Access 데이터 관리자 — 지침 디렉터리를 스캔해 키워드로 파일을 제공 + 병원 DB."""

import glob
import json
import math
import os

from . import config


class DataManager:
    def __init__(self):
        print("\n[Server] DataManager (Direct Access) 초기화...")
        self.current_pos = {"lat": 37.4979, "lon": 127.0276}
        self.file_map = {}
        self._load_hospital_db(config.HOSPITAL_DB)
        self._scan_filesystem(config.PROTOCOL_DIR)

    def _load_hospital_db(self, path):
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                self.hospital_db = json.load(f)
            print(f"[Server] 병원 {len(self.hospital_db)}곳 데이터 로드 완료.")
        else:
            print(f"[Warning] 병원 데이터 파일 없음: {path}")
            self.hospital_db = []

    def _scan_filesystem(self, protocol_dir):
        if not os.path.exists(protocol_dir):
            print(f"[Warning] 지정된 경로를 찾을 수 없음: {protocol_dir}")
        else:
            print(f"[Server] 프로토콜 파일 스캔 중... (Target: {protocol_dir})")
        files = glob.glob(os.path.join(protocol_dir, "**", "*.md"), recursive=True)
        for fp in files:
            fn = os.path.basename(fp)
            cn = os.path.splitext(fn)[0]
            self.file_map[fn] = fp
            self.file_map[cn] = fp
            self.file_map[cn.replace(" ", "")] = fp
        print(f"[Server] 총 {len(files)}개의 프로토콜 파일 매핑 완료.")

    def read_specific_files(self, target_names):
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
                        docs.append({
                            "source": os.path.basename(path),
                            "page": "Full Document",
                            "content": f.read(),
                        })
                except Exception as e:
                    print(f"[Error] 파일 읽기 실패 ({path}): {e}")
            else:
                print(f"[Warning] 요청한 파일을 찾을 수 없음: {name}")
        return docs

    def find_hospitals(self, dept):
        candidates = []
        for h in self.hospital_db:
            if any(dept in d or d in dept for d in h.get("dept", [])):
                dist = math.sqrt((h["lat"] - self.current_pos["lat"]) ** 2
                                 + (h["lon"] - self.current_pos["lon"]) ** 2) * 111
                candidates.append({**h, "dist_km": round(dist, 2)})
        candidates.sort(key=lambda x: x["dist_km"])
        return candidates[:3]
