<script setup lang="ts">
import { ref } from 'vue';
import { useRouter } from 'vue-router';
import { ArrowRight, Eye, EyeOff, LockKeyhole, Mail } from '@lucide/vue';
import { useSession } from '../stores/session';
import { useI18n } from '../i18n';

const session = useSession();
const { t } = useI18n();
const router = useRouter();
const mode = ref<'login'|'register'>('login');
const email = ref(''); const password = ref(''); const username = ref(''); const firstName = ref(''); const lastName = ref('');
const showPassword = ref(false); const pending = ref(false); const error = ref('');
const heroImageUrl = '/manus-storage/async-images/eLLpOfwpeXc3WwCKDskwLz/image-1.webp';
function fallbackPhoto(event: Event) {
  const image = event.target as HTMLImageElement;
  image.src = '/kawastock-shop-unsplash.jpg';
  image.onerror = null;
}
async function submit() {
  error.value = '';
  if (!email.value || !password.value) { error.value = 'Renseignez votre adresse e-mail et votre mot de passe.'; return; }
  if (mode.value === 'register' && !username.value) { error.value = 'Choisissez un nom d’utilisateur.'; return; }
  pending.value = true;
  try {
    if (mode.value === 'login') await session.login(email.value, password.value);
    else await session.register({ email: email.value, password: password.value, username: username.value, first_name: firstName.value, last_name: lastName.value });
    router.replace('/');
  } catch (e) { error.value = e instanceof Error ? e.message : 'Connexion impossible. Réessayez.'; }
  finally { pending.value = false; }
}
</script>

<template>
  <main class="auth-page"><section class="auth-story"><img class="auth-story-image" :src="heroImageUrl" :alt="t('Commerçante dans sa boutique, entourée de produits')" @error="fallbackPhoto" /><div class="auth-story-overlay"></div><div class="auth-brand"><div class="brand-mark"><span></span><span></span><span></span></div><span class="brand-name">kawa<span>stock</span></span></div><div class="story-content"><span class="story-kicker"><span class="kicker-line"></span> {{ t('LE QUOTIDIEN, MIEUX ORGANISÉ') }}</span><h1>{{ t('Tout votre commerce.') }}<br /><em>{{ t('En un regard.') }}</em></h1><p>{{ t('Stocks, ventes et achats réunis dans un espace simple, pensé pour les gens qui font tourner les boutiques.') }}</p><div class="story-stat"><div class="stat-stack"><span>✓</span><span>↗</span><span>⌂</span></div><span>{{ t('Votre activité, toujours à portée de main.') }}</span></div></div><div class="story-footer"><span>{{ t('GESTION • STOCK • VENTE') }}</span><span>© KAWASTOCK</span></div></section>
    <section class="auth-panel"><img class="auth-mobile-photo" :src="heroImageUrl" :alt="t('Boutique de proximité tenue par une commerçante')" @error="fallbackPhoto" /><div class="auth-panel-inner"><div class="auth-welcome"><span class="eyebrow">{{ t('VOTRE ESPACE, VOTRE RYTHME') }}</span><h2>{{ t(mode === 'login' ? 'Ravi·e de vous retrouver.' : 'Votre commerce, en mieux.') }}</h2><p>{{ t(mode === 'login' ? 'Connectez-vous pour retrouver votre activité.' : 'Créez votre compte et démarrez en quelques instants.') }}</p></div><form class="auth-form" @submit.prevent="submit">
      <label v-if="mode === 'register'">{{ t('Nom d’utilisateur') }}<input v-model="username" autocomplete="username" placeholder="ex. awa.kone" required /></label>
      <div v-if="mode === 'register'" class="form-row"><label>{{ t('Prénom') }}<input v-model="firstName" autocomplete="given-name" placeholder="Awa" /></label><label>{{ t('Nom') }}<input v-model="lastName" autocomplete="family-name" placeholder="Koné" /></label></div>
      <label>{{ t('Adresse e-mail') }}<div class="input-icon"><Mail :size="17" /><input v-model="email" type="email" autocomplete="email" placeholder="vous@exemple.com" required /></div></label>
      <label>{{ t('Mot de passe') }}<div class="input-icon"><LockKeyhole :size="17" /><input v-model="password" :type="showPassword ? 'text' : 'password'" :autocomplete="mode === 'login' ? 'current-password' : 'new-password'" :placeholder="t('8 caractères minimum')" required /><button type="button" class="input-action" :aria-label="t(showPassword ? 'Masquer' : 'Afficher')" @click="showPassword = !showPassword"><EyeOff v-if="showPassword" :size="17" /><Eye v-else :size="17" /></button></div></label>
      <p v-if="error" class="form-error">{{ t(error) }}</p><button class="button primary wide auth-submit" :disabled="pending">{{ pending ? t('Un instant…') : t(mode === 'login' ? 'Se connecter' : 'Créer mon compte') }}<ArrowRight v-if="!pending" :size="17" /></button>
    </form><p class="auth-switch">{{ t(mode === 'login' ? 'Vous découvrez KawaStock ?' : 'Vous avez déjà un compte ?') }} <button @click="mode = mode === 'login' ? 'register' : 'login'; error = ''">{{ t(mode === 'login' ? 'Créer un compte' : 'Se connecter') }}</button></p><div class="auth-security"><span class="security-dot"></span> {{ t('Connexion sécurisée à votre espace de travail') }}</div></div><div class="auth-mobile-mark"><div class="brand-mark"><span></span><span></span><span></span></div><span class="brand-name">kawa<span>stock</span></span></div></section>
  </main>
</template>
