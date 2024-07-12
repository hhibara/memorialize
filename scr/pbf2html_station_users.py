import os
import math
import pandas as pd
import geopandas as gpd
import folium
from shapely.geometry import Point, LineString
from mapbox_vector_tile import decode
import mercantile

def tile_to_latlon(x, y, z):
    """タイル座標をWGS84緯度経度に変換"""
    n = 2.0 ** z
    lon_deg = x / n * 360.0 - 180.0
    lat_rad = math.atan(math.sinh(math.pi * (1 - 2 * y / n)))
    lat_deg = math.degrees(lat_rad)
    return lon_deg, lat_deg

def read_pbf(file_path: str) -> dict:
    try:
        with open(file_path, 'rb') as f:
            data = f.read()
        
        tile = decode(data)
        if not tile:
            print(f"警告: ファイル {file_path} は空です。")
            return None
        
        layer = next(iter(tile.values()))
        
        # ファイル名からzoom、x、y座標を抽出
        file_name = os.path.basename(file_path)
        parts = file_name.split('_')
        z, x, y = map(int, [15, parts[-2], parts[-1].split('.')[0]])
        
        features = []
        for feature in layer['features']:
            properties = feature.get('properties', {})
            if 'S12_001_ja' in properties:
                # 乗降客数データを使用（ここでは2022年のデータ S12_009 を使用）
                passengers = properties.get('S12_009', 0)
                geom = feature['geometry']
                
                if geom['type'] == 'LineString':
                    # LineStringの場合、最初の座標を使用
                    coords = geom['coordinates'][0]
                elif geom['type'] == 'Polygon':
                    coords = geom['coordinates'][0][0]
                elif geom['type'] == 'Point':
                    coords = geom['coordinates']
                else:
                    print(f"警告: サポートされていないジオメトリタイプ: {geom['type']}")
                    continue
                
                lon, lat = tile_to_latlon(x + coords[0]/layer['extent'], y + coords[1]/layer['extent'], z)
                features.append({
                    'geometry': Point(lon, lat),
                    'properties': {
                        'name': properties['S12_001_ja'],
                        'passengers': passengers
                    }
                })
        
        print(f"ファイル {file_path} から抽出された有効なフィーチャー数: {len(features)}")
        return features
    except Exception as e:
        print(f"エラー: ファイル {file_path} の処理中に問題が発生しました: {str(e)}")
        return None

def load_all_pbf_files(directory: str) -> gpd.GeoDataFrame:
    all_data = []
    file_count = 0
    for file in os.listdir(directory):
        if file.endswith('.pbf'):
            file_count += 1
            file_path = os.path.join(directory, file)
            features = read_pbf(file_path)
            if features:
                all_data.extend(features)
    
    print(f"処理したファイル数: {file_count}")
    
    if all_data:
        gdf = gpd.GeoDataFrame(all_data)
        gdf.crs = "EPSG:4326"
        return gdf
    else:
        print("警告: 有効なデータが見つかりませんでした。")
        return gpd.GeoDataFrame()

def create_map(data: gpd.GeoDataFrame, center: list, zoom: int) -> folium.Map:
    m = folium.Map(location=center, zoom_start=zoom)
    
    # パッセンジャー数の範囲を計算
    min_passengers = data['properties'].apply(lambda x: x['passengers']).min()
    max_passengers = data['properties'].apply(lambda x: x['passengers']).max()

    for idx, row in data.iterrows():
        popup_text = f"駅名: {row['properties']['name']}<br>乗降客数: {row['properties']['passengers']}"
        
        # パッセンジャー数に基づいてマーカーサイズを調整
        size = 5 + (row['properties']['passengers'] - min_passengers) / (max_passengers - min_passengers) * 15
        
        folium.CircleMarker(
            location=[row.geometry.y, row.geometry.x],
            radius=size,
            popup=popup_text,
            color='red',
            fill=True,
            fill_color='red'
        ).add_to(m)
    
    return m

def main():
    pbf_dir = '500m_mesh/station_users_500m_mesh'
    center = [35.6852, 139.7528]  # 皇居の座標
    zoom = 11  # 東京23区全体が見えるように調整

    print("Loading PBF files...")
    all_data = load_all_pbf_files(pbf_dir)

    if all_data.empty:
        print("警告: 有効なデータが見つかりませんでした。")
    else:
        print(f"読み込んだ駅の数: {len(all_data)}")
        print(f"バウンディングボックス: {all_data.total_bounds}")
        
        m = create_map(all_data, center, zoom)
        m.save('tokyo_station_map.html')
        print("マップが tokyo_station_map.html として保存されました。")

if __name__ == "__main__":
    main()
