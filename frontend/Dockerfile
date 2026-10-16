FROM node:24-alpine
WORKDIR /app
ENV NODE_ENV=production
COPY --chown=node:node package.json server.js ./
COPY --chown=node:node public ./public
USER node
EXPOSE 3000
CMD ["node", "server.js"]
