FROM node:20-alpine

WORKDIR /app/web

COPY web/package.json /app/web/package.json
RUN npm install

COPY web /app/web

ENV API_PROXY_TARGET=http://backend:8000

EXPOSE 5173

CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0", "--port", "5173"]
