import { createApp } from 'vue';
import { createPinia } from 'pinia';
import App from './App.vue';
import router from './router';
import './styles.css';

createApp(App).use(createPinia()).use(router).mount('#app');

if (import.meta.env.PROD && 'serviceWorker' in navigator) {
  navigator.serviceWorker.register('/sw.js').catch(error => {
    console.error('Unable to register the KawaStock offline service worker.', error);
  });
}
