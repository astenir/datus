FROM node:22-slim

WORKDIR /app

COPY datus-web/package*.json ./
RUN npm config set registry https://registry.npmmirror.com \
    && npm ci --legacy-peer-deps

COPY datus-web ./

EXPOSE 5173

CMD ["npm", "run", "dev"]
