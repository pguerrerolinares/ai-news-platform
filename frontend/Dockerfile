FROM oven/bun:1-alpine AS frontend-build

WORKDIR /app
COPY package.json bun.lock ./
RUN bun install --frozen-lockfile
COPY . .
ARG PUBLIC_BASE_PATH="/ai-news/"
ARG VITE_API_URL="/ai-news"
ENV PUBLIC_BASE_PATH=$PUBLIC_BASE_PATH
ENV VITE_API_URL=$VITE_API_URL
RUN bun run build

FROM nginx:1.27-alpine AS frontend
COPY --from=frontend-build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
