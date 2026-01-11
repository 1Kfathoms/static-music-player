# 仕様・役割:
# 1. 指定フォルダ内の音楽ファイルをスキャン。
# 2. 'mutagen' ライブラリを使ってアルバムアートを抽出・保存。
# 3. ファイル名と画像パスをセットにした playlist.js を生成。
# 4. プレイヤー(index.html)を生成し、サーバーを起動（オプション）。

import os
import json
import argparse
import shutil
import http.server
import socketserver
import webbrowser
import hashlib

# 外部ライブラリチェック
try:
    import mutagen
    from mutagen import File
    from mutagen.mp4 import MP4
    from mutagen.id3 import ID3, APIC
    HAS_MUTAGEN = True
except ImportError:
    HAS_MUTAGEN = False

# 保存するフォルダ名を定義（隠しフォルダにしない）
COVERS_DIR = "covers"

def extract_cover(file_path, covers_dir_path):
    """
    音楽ファイルからアートワークを抽出し、covers_dir_pathに保存してそのパスを返す。
    画像がない、またはエラーの場合は None を返す。
    """
    if not HAS_MUTAGEN:
        return None

    try:
        audio = File(file_path)
        if not audio:
            return None

        # 一意なファイル名を作る (パスのハッシュ値)
        file_hash = hashlib.md5(file_path.encode('utf-8')).hexdigest()
        image_data = None
        ext = ""

        # m4a (MP4) の場合
        if 'covr' in audio.tags:
            image_data = audio.tags['covr'][0]
            # m4aのcovrは通常 jpeg か png
            ext = ".jpg" # 簡易的にjpgとする

        # mp3 (ID3) の場合
        elif hasattr(audio, 'tags') and isinstance(audio.tags, ID3):
            for tag in audio.tags.values():
                if isinstance(tag, APIC):
                    image_data = tag.data
                    if 'png' in tag.mime: ext = ".png"
                    else: ext = ".jpg"
                    break
        
        # FLACなど他の形式は簡易対応として省略

        if image_data:
            cover_filename = f"{file_hash}{ext}"
            cover_path = os.path.join(covers_dir_path, cover_filename)
            
            # すでに抽出済みならスキップ（高速化）
            if not os.path.exists(cover_path):
                with open(cover_path, 'wb') as f:
                    f.write(image_data)
            
            # HTMLから参照するための相対パスを返す (COVERS_DIR定数を使用)
            return f"{COVERS_DIR}/{cover_filename}"

    except Exception as e:
        print(f"Cover extract error ({os.path.basename(file_path)}): {e}")
    
    return None

def main():
    if not HAS_MUTAGEN:
        print("警告: 'mutagen' ライブラリが見つかりません。")
        print("画像を抽出するには 'pip install mutagen' を実行してください。")
        print("※ 画像なしモードで続行します...")

    parser = argparse.ArgumentParser(description="Generate music player with Album Art.")
    parser.add_argument("folder", nargs="?", help="Target music folder path")
    parser.add_argument("--port", type=int, default=8000, help="Server port")
    parser.add_argument("--no-server", action="store_true", help="Do not start server")
    args = parser.parse_args()

    # テンプレート確認
    script_dir = os.path.dirname(os.path.abspath(__file__))
    template_path = os.path.join(script_dir, "player_template.html")
    if not os.path.exists(template_path):
        print("エラー: player_template.html が見つかりません。")
        return

    # 対象フォルダ
    target_dir = args.folder
    if not target_dir:
        print("音楽ファイルがあるフォルダのパスを入力:")
        target_dir = input("> ").strip().strip('"').strip("'")

    if not os.path.isdir(target_dir):
        print(f"エラー: ディレクトリが見つかりません: {target_dir}")
        return

    # カバー画像保存用フォルダを作成 (COVERS_DIR定数を使用)
    covers_path = os.path.join(target_dir, COVERS_DIR)
    if HAS_MUTAGEN and not os.path.exists(covers_path):
        os.makedirs(covers_path)

    # スキャン
    supported_extensions = ('.m4a', '.mp3', '.aac', '.ogg', '.wav')
    files = [f for f in os.listdir(target_dir) if f.lower().endswith(supported_extensions) and not f.startswith('.')]
    files.sort()

    print(f"対象フォルダ: {target_dir}")
    print(f"検出ファイル: {len(files)} 曲")
    if HAS_MUTAGEN:
        print(f"アートワーク抽出中... (保存先: {COVERS_DIR}/)")

    # データ構築
    playlist_data = []
    for f in files:
        full_path = os.path.join(target_dir, f)
        # 修正: extract_cover に渡すパス変数を統一
        cover_rel_path = extract_cover(full_path, covers_path)
        
        # JS側で扱いやすいオブジェクト構造にする
        playlist_data.append({
            "name": f,
            "url": f, # URLエンコードはJS側でやるのでそのまま
            "cover": cover_rel_path # 画像がない場合は None
        })

    # JS書き出し
    js_dest_path = os.path.join(target_dir, "playlist.js")
    js_content = f"const LOCAL_FILES = {json.dumps(playlist_data, ensure_ascii=False, indent=2)};"
    
    try:
        with open(js_dest_path, 'w', encoding='utf-8') as f:
            f.write(js_content)
    except Exception as e:
        print(f"エラー (playlist.js): {e}")
        return

    # HTMLコピー
    html_dest_path = os.path.join(target_dir, "index.html")
    try:
        shutil.copy2(template_path, html_dest_path)
        print("✔ 生成完了")
    except Exception as e:
        print(f"エラー (index.html): {e}")
        return

if __name__ == "__main__":
    main()