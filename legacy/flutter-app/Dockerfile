FROM nginx:stable-alpine
COPY build/web /usr/share/nginx/html
RUN sed -i 's/80/8080/g' /etc/nginx/conf.d/default.conf
EXPOSE 8080
CMD ["nginx", "-g", "daemon off;"]
