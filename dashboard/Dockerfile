# Stage 1: Build React frontend
FROM node:20-alpine AS frontend-build
WORKDIR /build
COPY dashboard/frontend/package*.json ./
RUN npm install
COPY dashboard/frontend/ ./
RUN npm run build

# Stage 2: Python backend + full repo + git
FROM python:3.11-slim
WORKDIR /repo

# Install git (needed for agent file commit+push) and ffmpeg (server-side
# outreach videos — backend/outreach_video.py)
RUN apt-get update && apt-get install -y git ffmpeg --no-install-recommends && rm -rf /var/lib/apt/lists/*

# Copy entire repo so agent directories are accessible
COPY . .

# Install Python deps (dashboard + all agents run in this container)
RUN pip install --no-cache-dir \
    -r dashboard/backend/requirements.txt \
    -r leadgen-agent/requirements.txt \
    -r apptset-agent/requirements.txt

# Headless Chromium + its system libs for outreach_video.py's site screenshots
RUN python -m playwright install --with-deps chromium

# Copy built frontend into the location the backend serves from
COPY --from=frontend-build /build/dist ./dashboard/backend/frontend/dist

WORKDIR /repo/dashboard/backend

EXPOSE 8000
CMD uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}
