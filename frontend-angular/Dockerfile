FROM node:26-alpine AS build

WORKDIR /workspace/frontend-angular

COPY frontend-angular/package.json frontend-angular/package-lock.json ./
RUN npm ci

COPY frontend-angular/ ./
RUN npm run build

FROM nginx:alpine

COPY frontend-angular/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /workspace/frontend-angular/dist/frontend-angular/browser/ /usr/share/nginx/html/

EXPOSE 80
