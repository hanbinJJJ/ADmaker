import os
import openai
import requests
from flask import Flask, render_template, request, jsonify
from dotenv import load_dotenv  # .env 파일에서 환경 변수 로드

# .env 파일에서 환경 변수 로드
load_dotenv()

# OpenAI API 키 설정 (환경 변수에서 API 키를 가져옵니다)
openai.api_key = os.getenv('OPENAI_API_KEY')

app = Flask(__name__)

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
def main():
    return render_template('main.html')

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

if __name__ == '__main__':
    # static/images 폴더가 없다면 생성
    if not os.path.exists('static/images'):
        os.makedirs('static/images')
    app.run(debug=True)