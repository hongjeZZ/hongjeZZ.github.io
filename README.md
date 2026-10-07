# hongjeZZ.github.io

백엔드·인프라·Kubernetes·JVM·이벤트 스트리밍을 공부하며 정리하는 개발 블로그. https://hongjeZZ.github.io

## 구성

- Jekyll 4.3 + `jekyll-feed`·`jekyll-seo-tag`·`jekyll-sitemap`. 별도 테마 gem 없음.
- 레이아웃 `_layouts/`(default·home·page·post) + 단일 CSS `assets/css/style.css`.
- 글은 `_posts/YYYY-MM-DD-slug.md`, permalink `/posts/:title/`.
- 커버 이미지는 본문 첫 이미지(`assets/img/<slug>/`)를 홈 썸네일로 자동 사용.

## 로컬 실행 (Docker, 시스템 Ruby 불필요)

- `./bin/serve` — http://localhost:4000 미리보기, 저장 시 자동 새로고침
- `./bin/build` — CI와 동일한 프로덕션 빌드 + htmlproofer 검사

## 배포

`main`에 push되면 `.github/workflows/pages-deploy.yml`이 빌드·htmlproofer 검사 후 GitHub Pages에 배포한다. PR은 빌드·검사만 수행한다.
