# LocalBiz Intelligence Frontend (placeholder)

> 이정원 FE 합류 전 자리표시자. 실제 Next.js + Three.js 스켈레톤은 합류 후 초기화 예정.

## 예정 스택

- Next.js 14 (App Router)
- Three.js / react-three-fiber
- TypeScript
- Vercel 배포

## 예정 WS 응답 블록 16종 렌더링 대상

intent / text / text_stream / place / places / events / course /
map_markers / map_route / chart / calendar / references /
analysis_sources / disambiguation / done / error

자세한 블록 스펙은 `기획/서비스 통합 기획서` §4.5 참조.

## 디렉토리 (예정)

```
frontend/
├── app/          # Next.js App Router
├── components/   # UI 컴포넌트 + 16 블록 렌더러
├── three/        # Three.js 씬 / Cluster 시각화
├── lib/          # WS 클라이언트, 훅
└── styles/       # Tailwind / design tokens
```

## fe-visual 워커 대상

본 README 및 `frontend/**` 이하 모든 파일이 `.claude/agents/fe-visual.md` 워커의 유일한 작업 범위다.
