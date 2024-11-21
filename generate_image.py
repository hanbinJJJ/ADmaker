import sys
import os
from diffusers import StableDiffusionPipeline
import torch

# Stable Diffusion 모델 로드
pipe = StableDiffusionPipeline.from_pretrained("stabilityai/stable-diffusion-2-1-base", 
                                               torch_dtype=torch.float16)
pipe = pipe.to("cuda")  # GPU를 사용할 경우

# 사용자로부터 광고 텍스트 받기
ad_text = sys.argv[1]

# 이미지 생성
image = pipe(ad_text).images[0]

# 이미지 파일 저장 경로 설정
output_dir = os.path.join(os.path.dirname(__file__), 'static', 'images')
if not os.path.exists(output_dir):
    os.makedirs(output_dir)

# 파일명 생성 (광고 텍스트의 처음 10글자를 파일명으로 사용)
image_filename = f"{ad_text[:10]}.png"
image_path = os.path.join(output_dir, image_filename)

# 이미지 저장
image.save(image_path)

# 파일 경로 출력 (Flask에서 이 경로를 받아 사용)
print(image_filename)
