import os
import openai
import requests
from flask import Flask, render_template, request, jsonify, session
from dotenv import load_dotenv  # .env 파일에서 환경 변수 로드
from datetime import datetime
import json
import uuid
import re
import base64
from io import BytesIO
from PIL import Image

# .env 파일에서 환경 변수 로드
load_dotenv()

# OpenAI API 키 설정 (환경 변수에서 API 키를 가져옵니다)
openai.api_key = os.getenv('OPENAI_API_KEY')

app = Flask(__name__)
app.secret_key = 'your-secret-key'  # 세션을 위한 시크릿 키

# 방문자 수를 저장할 JSON 파일 경로
VISITOR_FILE = 'visitors.json'

# 조회수와 좋아요 데이터를 저장할 파일 경로
STATS_FILE = 'data/image_stats.json'

def load_visitor_data():
    if os.path.exists(VISITOR_FILE):
        with open(VISITOR_FILE, 'r') as f:
            return json.load(f)
    return {'total': 0, 'today': 0, 'last_reset': str(datetime.now().date())}

def save_visitor_data(data):
    with open(VISITOR_FILE, 'w') as f:
        json.dump(data, f)

def load_image_stats():
    stats_file = os.path.join('data', 'image_stats.json')
    if os.path.exists(stats_file):
        with open(stats_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def save_image_stats(stats):
    stats_file = os.path.join('data', 'image_stats.json')
    os.makedirs(os.path.dirname(stats_file), exist_ok=True)
    with open(stats_file, 'w', encoding='utf-8') as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)

@app.before_request
def count_visitor():
    # 방문자 데이터 로드
    visitor_data = load_visitor_data()
    
    # 날짜가 바뀌었으면 today 카운트 리셋
    today = str(datetime.now().date())
    if visitor_data['last_reset'] != today:
        visitor_data['today'] = 0
        visitor_data['last_reset'] = today

    # 새로운 세션인 경우에만 카운트
    if 'visited' not in session:
        session['visited'] = True
        visitor_data['total'] += 1
        visitor_data['today'] += 1
        save_visitor_data(visitor_data)

# 광고 이미지 생성 함수
def generate_image(ad_text):
    try:
        response = openai.Image.create(
            prompt=ad_text,  # 생성할 광고 이미지의 설명
            n=1,
            size="1024x1024"
        )
        image_url = response['data'][0]['url']
        
        # 이미지를 다운로드하고 저장 (static/images 폴더에 저장)
        image_filename = f"{ad_text[:10]}.png"
        img_data = requests.get(image_url).content
        image_path = os.path.join('static', 'images', image_filename)
        with open(image_path, 'wb') as handler:
            handler.write(img_data)
        return image_filename
    except Exception as e:
        print("Error generating image:", e)
        return None

# 광고 텍스트 생성 함수 (gpt-3.5-turbo 모델 사용)
def generate_ad_text(user_input):
    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "당신은 광고 카피라이터입니다. 한국어로 광고 문구를 작성하세요."},
                {"role": "user", "content": f"다음 입력을 바탕으로 광고를 생성하세요: {user_input}"}
            ],
            max_tokens=60,
            temperature=0.7
        )
        return response.choices[0].message['content'].strip()
    except Exception as e:
        print("Error generating ad text:", e)
        return "광고 문구 생성 중 오류가 발생했습니다."

@app.route('/')
def home():
    return render_template('main.html')

@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/create')
def create():
    return render_template('index.html')

@app.route('/api/ads')
def get_ads():
    try:
        # static/images 디렉토리의 경로
        images_dir = os.path.join('static', 'images')
        
        # 이미지 파일 목록 가져오기 (.png 파일만)
        image_files = [f for f in os.listdir(images_dir) if f.endswith('.png')]
        
        # 이미지 URL 리스트 생성
        ads = [
            {
                'image_url': f'/static/images/{image_file}'
            }
            for image_file in image_files
        ]
        
        return jsonify(ads)
    except Exception as e:
        print("Error fetching ads:", e)
        return jsonify({'error': 'Failed to fetch ads'}), 500

# 광고 생성 라우트 (POST)
@app.route('/generate_ad', methods=['POST'])
def generate_ad():
    data = request.get_json()
    user_input = data.get('user_input', '')

    # 광고 텍스트 생성 (한글 지원)
    ad_text = generate_ad_text(user_input)
    
    if ad_text == "광고 문구 생성 중 오류가 발생했습니다.":
        return jsonify({'error': 'Failed to generate ad text'}), 500

    # 광고 이미지 생성 (한글 프롬프트 사용)
    image_filename = generate_image(f"광고: {ad_text}")
    
    if not image_filename:
        return jsonify({'error': 'Failed to generate ad image'}), 500

    # 올바른 JSON 응답을 반환합니다.
    return jsonify({
        'ad_text': ad_text,
        'image_url': f'/static/images/{image_filename}'
    })

# 광고 수정 라우트 (POST)
@app.route('/modify_ad', methods=['POST'])
def modify_ad():
    data = request.get_json()
    user_input = data.get('user_input', '')

    # 광고 텍스트 재생성 (한글 지원)
    ad_text = generate_ad_text(user_input)
    
    if ad_text == "광고 문구 생성 중 오류가 발생했습니다.":
        return jsonify({'error': 'Failed to generate ad text'}), 500

    # 광고 이미지 재생성 (한글 프롬프트 사용)
    image_filename = generate_image(f"광고: {ad_text}")
    
    if not image_filename:
        return jsonify({'error': 'Failed to generate ad image'}), 500
    
    return jsonify({
        'ad_text': ad_text,
        'image_url': f'/static/images/{image_filename}'
    })

# 추가 요구사항 반영 광고 생성 라우트 (POST)
@app.route('/add_requirements', methods=['POST'])
def add_requirements():
    data = request.get_json()
    user_requirements = data.get('user_requirements', '')

    # 광고 텍스트 수정 (한글 지원)
    ad_text = f"추가 요구 사항을 반영한 광고: {user_requirements}"
    
    # 광고 이미지 생성 (한글 프롬프트 사용)
    image_filename = generate_image(f"광고: {ad_text}")
    
    if not image_filename:
        return jsonify({'error': 'Failed to generate ad image'}), 500
    
    return jsonify({
        'ad_text': ad_text,
        'image_url': f'/static/images/{image_filename}'
    })

@app.route('/api/image-count')
def get_image_count():
    # static/images 폴더의 이미지 파일 수 계산
    image_dir = os.path.join(app.static_folder, 'images')
    image_count = len([f for f in os.listdir(image_dir) 
                      if f.endswith(('.jpg', '.png', '.jpeg'))])
    return jsonify({'count': image_count})

@app.route('/api/user-count')
def get_user_count():
    visitor_data = load_visitor_data()
    return jsonify({
        'total': visitor_data['total'],
        'today': visitor_data['today']
    })

@app.route('/api/today-count')
def get_today_count():
    # 오늘 생성된 이미지 수 조회
    today = datetime.now().date()
    # 예시: today_count = db.session.query(Image).filter(
    #     func.date(Image.created_at) == today
    # ).count()
    today_count = get_today_image_count_from_db()  # 실제 구현 필요
    return jsonify({'count': today_count})

@app.route('/gallery')
def gallery():
    return render_template('gallery.html')

@app.route('/api/gallery-images')
def get_gallery_images():
    try:
        images_dir = os.path.join('static', 'images')
        stats = load_image_stats()  # 이미지 통계 로드
        image_files = [f for f in os.listdir(images_dir) if f.endswith(('.png', '.jpg', '.jpeg'))]
        
        gallery_images = []
        for image_file in image_files:
            file_path = os.path.join(images_dir, image_file)
            creation_time = os.path.getctime(file_path)
            created_at = datetime.fromtimestamp(creation_time)
            
            # 실제 조회수와 좋아요 수 사용
            image_stats = stats.get(image_file, {'views': 0, 'likes': 0})
            
            gallery_images.append({
                'url': f'/static/images/{image_file}',
                'filename': image_file,
                'title': image_file.split('.')[0],
                'created_at': created_at.strftime('%Y-%m-%d %H:%M'),
                'views': image_stats.get('views', 0),
                'likes': image_stats.get('likes', 0)
            })
        
        gallery_images.sort(key=lambda x: x['created_at'], reverse=True)
        
        return jsonify(gallery_images)
    except Exception as e:
        print("Error fetching gallery images:", e)
        return jsonify({'error': 'Failed to fetch gallery images'}), 500

# 댓글 관련 함수 추가
def load_comments(image_id):
    comments_dir = os.path.join('data', 'comments')
    comments_file = os.path.join(comments_dir, f'comments_{image_id}.json')
    
    if os.path.exists(comments_file):
        with open(comments_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    return []

def save_comments(image_id, comments):
    comments_dir = os.path.join('data', 'comments')
    os.makedirs(comments_dir, exist_ok=True)
    
    comments_file = os.path.join(comments_dir, f'comments_{image_id}.json')
    with open(comments_file, 'w', encoding='utf-8') as f:
        json.dump(comments, f, ensure_ascii=False, indent=2)

@app.route('/gallery/<image_id>')
def image_detail(image_id):
    stats = load_image_stats()
    
    if image_id not in stats:
        stats[image_id] = {
            'views': 0,
            'likes': 0,
            'created_at': datetime.now().strftime('%Y-%m-%d %H:%M')
        }
    
    # 조회수 증가
    stats[image_id]['views'] += 1
    save_image_stats(stats)
    
    return render_template('image_detail.html', 
                         image_id=image_id,
                         stats=stats[image_id],
                         comments=load_comments(image_id))

@app.route('/api/comments/<image_id>', methods=['POST'])
def add_comment(image_id):
    try:
        data = request.json
        nickname = data.get('nickname', '익명')
        comment = data.get('comment')
        
        if not comment:
            return jsonify({'error': 'Comment is required'}), 400
            
        # 새 댓글 생성
        new_comment = {
            'id': str(uuid.uuid4()),
            'nickname': nickname,
            'comment': comment,
            'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        
        # 기존 댓글 불러오기
        comments = load_comments(image_id)
        comments.append(new_comment)
        
        # 댓글 저장
        save_comments(image_id, comments)
            
        return jsonify(new_comment)
    except Exception as e:
        print(f"Error adding comment: {e}")
        return jsonify({'error': 'Failed to add comment'}), 500

@app.route('/api/like/<image_id>', methods=['POST'])
def toggle_like(image_id):
    try:
        stats = load_image_stats()
        if image_id not in stats:
            stats[image_id] = {
                'views': 0,
                'likes': 0,
                'created_at': datetime.now().strftime('%Y-%m-%d %H:%M')
            }
        
        stats[image_id]['likes'] += 1
        save_image_stats(stats)
        
        return jsonify({
            'likes': stats[image_id]['likes']
        })
    except Exception as e:
        print(f"Error toggling like: {e}")
        return jsonify({'error': 'Failed to toggle like'}), 500

@app.route('/admin')
def admin():
    # 이미지 파일들 가져오기
    image_folder = os.path.join('static', 'images')
    images = []
    stats = load_image_stats()
    
    if os.path.exists(image_folder):
        for filename in os.listdir(image_folder):
            if filename.endswith(('.png', '.jpg', '.jpeg')):
                file_path = os.path.join(image_folder, filename)
                created_time = datetime.fromtimestamp(os.path.getctime(file_path))
                
                # 이미지 통계 가져오기
                image_stats = stats.get(filename, {'views': 0, 'likes': 0})
                
                # 해당 이미지의 댓글 수 계산
                comments = load_comments(filename)
                
                images.append({
                    'id': filename,
                    'url': f'/static/images/{filename}',
                    'created_at': created_time.strftime('%Y-%m-%d %H:%M'),
                    'likes': image_stats.get('likes', 0),
                    'views': image_stats.get('views', 0),
                    'comments': len(comments)
                })
    
    # 최신순으로 정렬
    images.sort(key=lambda x: x['created_at'], reverse=True)
    
    # 방문자 통계
    visitor_data = load_visitor_data()
    
    # 통계 데이터
    stats = {
        'total_ads': len(images),
        'today_ads': sum(1 for img in images if img['created_at'].startswith(datetime.now().strftime('%Y-%m-%d'))),
        'total_visitors': visitor_data['total'],
        'today_visitors': visitor_data['today'],
        'total_comments': sum(len(load_comments(img['id'])) for img in images),
        'today_comments': sum(
            len([c for c in load_comments(img['id']) 
                if c['created_at'].startswith(datetime.now().strftime('%Y-%m-%d'))])
            for img in images
        )
    }
    
    # 모든 댓글 가져오기
    all_comments = []
    for img in images:
        comments = load_comments(img['id'])
        for comment in comments:
            comment['image_id'] = img['id']
            all_comments.append(comment)
    
    # 댓글을 최신순으로 정렬
    all_comments.sort(key=lambda x: x['created_at'], reverse=True)
    
    return render_template('admin.html', 
                         stats=stats,
                         images=images,
                         comments=all_comments)

# 이미지 삭제 API
@app.route('/api/admin/images/<image_id>', methods=['DELETE'])
def delete_image(image_id):
    try:
        # 이미지 파일 삭제
        image_path = os.path.join('static', 'images', image_id)
        if os.path.exists(image_path):
            os.remove(image_path)
            
            # 이미지 통계 삭제
            stats = load_image_stats()
            if image_id in stats:
                del stats[image_id]
                save_image_stats(stats)
            
            # 이미지 댓글 삭제
            comments_path = os.path.join('data', 'comments', f'comments_{image_id}.json')
            if os.path.exists(comments_path):
                os.remove(comments_path)
                
            return jsonify({'success': True})
            
        return jsonify({'success': False, 'error': 'Image not found'})
    except Exception as e:
        print(f"Error deleting image: {e}")
        return jsonify({'success': False, 'error': str(e)})

# 댓글 삭제 API
@app.route('/api/admin/comments/<image_id>/<comment_id>', methods=['DELETE'])
def delete_comment(image_id, comment_id):
    try:
        comments = load_comments(image_id)
        comments = [c for c in comments if c['id'] != comment_id]
        save_comments(image_id, comments)
        return jsonify({'success': True})
    except Exception as e:
        print(f"Error deleting comment: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/generate_background', methods=['POST'])
def generate_background():
    try:
        data = request.get_json()
        base_prompt = data.get('prompt', '').strip()
        width = int(data.get('width', 1024))
        height = int(data.get('height', 1024))
        style = data.get('style', '')
        color_mood = data.get('colorMood', '')
        image_mood = data.get('imageMood', '')
        complexity = data.get('complexity', '')
        layout = data.get('layout', '')

        # DALL-E 3가 지원하는 크기 선택
        if width/height > 1:  # 가로가 더 긴 경우
            dalle_size = "1024x1024"  # 임시로 정사각형 사용
        else:  # 세로가 더 길거나 같은 경우
            dalle_size = "1024x1024"
            
        # 프롬프트 조합
        prompt = f"""Create a professional advertisement background image with the following specifications:
        Main description: {base_prompt}
        Style: {style}
        Color theme: {color_mood}
        Mood: {image_mood}
        Complexity: {complexity}
        Layout: {layout}
        
        The image should be:
        - Clean and high-quality
        - Suitable for text overlay
        - Professional and modern looking
        - Well-balanced composition
        - Maintain visual hierarchy
        """

        # DALL-E API 호출
        response = openai.Image.create(
            prompt=prompt,
            n=1,
            size="1024x1024",  # 고정된 크기 사용
            quality="standard",
            response_format="url"
        )
        
        image_url = response['data'][0]['url']
        
        # 이미지 저장
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        image_filename = f"bg_{timestamp}.png"
        image_path = os.path.join('static', 'images', image_filename)
        
        # 이미지 다운로드 및 저장
        img_response = requests.get(image_url)
        if img_response.status_code == 200:
            with open(image_path, 'wb') as f:
                f.write(img_response.content)
        
        return jsonify({
            'image_url': f'/static/images/{image_filename}'
        })
        
    except Exception as e:
        print(f"Error in generate_background: {str(e)}")
        return jsonify({
            'error': 'Failed to generate image'
        }), 500

# 수정사항을 반영한 이미지 생성 라우트 추가
@app.route('/generate_variations', methods=['POST'])
def generate_variations():
    try:
        # static/images 폴더의 테스트 이미지 사용
        test_images = [
            '/static/images/test1.jpg',
            '/static/images/test2.jpg',
            '/static/images/test3.jpg'
        ]
        
        return jsonify({
            'variations': test_images
        })

    except Exception as e:
        print(f"Error in generate_variations: {str(e)}")
        return jsonify({
            'error': 'Failed to generate image variations'
        }), 500

@app.route('/generate_ad_copy', methods=['POST'])
def generate_ad_copy():
    try:
        data = request.get_json()
        prompt = data.get('prompt', '')
        tone = data.get('tone', 'casual')
        
        # 톤에 따른 프롬프트 조정
        tone_descriptions = {
            'casual': '친근하고 편안한 톤으로',
            'professional': '전문적이고 신뢰감 있는 톤으로',
            'witty': '재치있고 유머러스한 톤으로',
            'emotional': '감성적��고 공감되는 톤으로',
            'direct': '간단명료하고 직관적인 톤으로'
        }
        
        # GPT 프롬프트 구성
        system_prompt = f"""당신은 전문 광고 카피라이터입니다. 
다음 제품/서비스에 대해 {tone_descriptions[tone]} 3개의 광고 문구를 생성해주세요.
- 각 문구는 20자 내외로 간결하게 작성
- 핵심 가치와 장점을 부각
- 기억하기 쉽고 임팩트 있게"""

        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=200
        )

        # 응답 텍스트를 줄바꿈으로 분리하여 리스트로 변환
        ad_copies = response.choices[0].message['content'].strip().split('\n')
        # 빈 문자열 제거 및 번호/기호 등 제거
        ad_copies = [re.sub(r'^[\d\s\.\-]+', '', copy.strip()) for copy in ad_copies if copy.strip()]
        
        return jsonify({
            'copies': ad_copies[:3]  # 최대 3개의 문구만 반환
        })

    except Exception as e:
        print("Error generating ad copy:", e)
        return jsonify({
            'error': 'Failed to generate ad copy'
        }), 500

@app.route('/save_ad', methods=['POST'])
def save_ad():
    try:
        data = request.get_json()
        title = data.get('title')
        image_data = data.get('imageData')

        # 파일명 생성 (공백은 언더스코어로 변경)
        filename = f"{title.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        
        # base64 이미지 데이터 처리
        image_data = image_data.split(',')[1]
        image_bytes = base64.b64decode(image_data)
        
        # 이미지 저장
        image_path = os.path.join('static', 'images', filename)
        with open(image_path, 'wb') as f:
            f.write(image_bytes)

        return jsonify({
            'success': True,
            'image_url': f'/static/images/{filename}'
        })

    except Exception as e:
        print(f"Error saving ad: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Failed to save ad'
        }), 500

if __name__ == '__main__':
    # static/images 폴더가 없다면 생성
    if not os.path.exists('static/images'):
        os.makedirs('static/images')
    app.run(debug=True)