FROM nginx:1.27-alpine

COPY nginx.conf /etc/nginx/nginx.conf
COPY upstream.conf /etc/nginx/conf.d/upstream.conf

CMD ["nginx", "-g", "daemon off;"]