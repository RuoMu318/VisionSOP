FROM node:24-alpine AS build

WORKDIR /app
COPY apps/web-ui/package.json apps/web-ui/package-lock.json ./
RUN npm ci
COPY apps/web-ui ./
RUN npm run build

FROM nginx:1.29-alpine
COPY deploy/nginx/default.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
