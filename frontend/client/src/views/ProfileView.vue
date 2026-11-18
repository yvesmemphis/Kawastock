<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue';
import { BadgeCheck, Camera, CircleAlert, LoaderCircle, Save, UserRound } from '@lucide/vue';
import { patch, request } from '../api/http';
import { useI18n } from '../i18n';
import { isOnline } from '../offline';
import { useSession } from '../stores/session';

const session = useSession();
const { t } = useI18n();
const profile = ref({
  first_name: session.user?.first_name || '',
  last_name: session.user?.last_name || '',
  theme: session.user?.theme || 'light',
  language: session.user?.language || 'fr',
});
const shopSettings = ref({
  currency: session.shop?.currency || 'XOF',
  default_min_stock: session.shop?.default_min_stock || '0',
});
const selectedPhoto = ref<File | null>(null);
const photoPreview = ref('');
const profilePending = ref(false);
const shopPending = ref(false);
const error = ref('');
const success = ref('');
const canEditShop = computed(() => session.role === 'owner');
const avatarUrl = computed(() => photoPreview.value || session.user?.profile_photo_url || '');

watch(() => session.user, user => {
  if (!user) return;
  profile.value = { first_name: user.first_name, last_name: user.last_name, theme: user.theme, language: user.language };
}, { immediate: true });

watch(() => session.shop, shop => {
  if (!shop) return;
  shopSettings.value = { currency: shop.currency, default_min_stock: shop.default_min_stock };
}, { immediate: true });

onBeforeUnmount(() => {
  if (photoPreview.value.startsWith('blob:')) URL.revokeObjectURL(photoPreview.value);
});

function choosePhoto(event: Event) {
  if (!isOnline.value) return;
  const file = (event.target as HTMLInputElement).files?.[0] || null;
  error.value = '';
  if (!file) return;
  if (!['image/jpeg', 'image/png', 'image/webp'].includes(file.type)) {
    error.value = t('Choisis une image PNG, JPG ou WebP.');
    return;
  }
  if (file.size > 5 * 1024 * 1024) {
    error.value = t('La photo doit faire 5 Mo maximum.');
    return;
  }
  if (photoPreview.value.startsWith('blob:')) URL.revokeObjectURL(photoPreview.value);
  selectedPhoto.value = file;
  photoPreview.value = URL.createObjectURL(file);
}

async function saveProfile() {
  if (!isOnline.value) return;
  profilePending.value = true;
  error.value = '';
  success.value = '';
  try {
    await patch('auth/me/', profile.value);
    if (selectedPhoto.value) {
      const body = new FormData();
      body.append('profile_photo', selectedPhoto.value);
      await request('auth/me/', { method: 'PATCH', body });
      selectedPhoto.value = null;
    }
    await session.loadProfile();
    if (photoPreview.value.startsWith('blob:')) URL.revokeObjectURL(photoPreview.value);
    photoPreview.value = '';
    success.value = t('Profil mis à jour.');
  } catch (e) {
    error.value = e instanceof Error ? t(e.message) : t('Enregistrement impossible.');
  } finally {
    profilePending.value = false;
  }
}

async function saveShopSettings() {
  if (!session.activeShopId || !canEditShop.value || !isOnline.value) return;
  shopPending.value = true;
  error.value = '';
  success.value = '';
  try {
    await patch(`shops/${session.activeShopId}/`, shopSettings.value);
    await session.loadProfile();
    success.value = t('Paramètres du commerce mis à jour.');
  } catch (e) {
    error.value = e instanceof Error ? t(e.message) : t('Enregistrement impossible.');
  } finally {
    shopPending.value = false;
  }
}
</script>

<template>
  <div class="page-heading">
    <div><span class="eyebrow">{{ t('Préférences') }}</span><h1>{{ t('Profil & paramètres') }}<span class="heading-period">.</span></h1></div>
  </div>
  <div v-if="error" class="notice notice-error"><CircleAlert :size="17" /><span>{{ error }}</span></div>
  <div v-if="success" class="notice notice-success"><BadgeCheck :size="17" /><span>{{ success }}</span></div>

  <div class="profile-settings-grid">
    <section class="panel profile-settings-card">
      <div class="panel-heading"><div><span class="eyebrow">{{ t('Profil') }}</span><h2>{{ t('Profil') }}</h2></div><UserRound :size="20" /></div>
      <div class="profile-photo-control">
        <div class="profile-photo-preview">
          <img v-if="avatarUrl" :src="avatarUrl" :alt="t('Photo de profil')" />
          <UserRound v-else :size="28" />
        </div>
        <label class="button secondary photo-picker" :class="{ disabled: !isOnline }"><Camera :size="16" />{{ t('Choisir une photo') }}<input type="file" accept="image/png,image/jpeg,image/webp" :disabled="!isOnline" @change="choosePhoto" /></label>
      </div>
      <form class="modal-form profile-form" @submit.prevent="saveProfile">
        <div class="form-row">
          <label>{{ t('Prénom') }}<input v-model="profile.first_name" autocomplete="given-name" :disabled="!isOnline" /></label>
          <label>{{ t('Nom') }}<input v-model="profile.last_name" autocomplete="family-name" :disabled="!isOnline" /></label>
        </div>
        <label>{{ t('Adresse e-mail') }}<input :value="session.user?.email" type="email" disabled /></label>
        <div class="form-row">
          <label>{{ t('Thème') }}<select v-model="profile.theme" :disabled="!isOnline"><option value="light">{{ t('Clair') }}</option><option value="dark">{{ t('Sombre') }}</option></select></label>
          <label>{{ t('Langue') }}<select v-model="profile.language" :disabled="!isOnline"><option value="fr">{{ t('Français') }}</option><option value="en">{{ t('English') }}</option></select></label>
        </div>
        <div class="modal-actions"><span></span><button class="button primary" type="submit" :disabled="profilePending || !isOnline"><LoaderCircle v-if="profilePending" class="spin" :size="16" /><Save v-else :size="16" />{{ t('Enregistrer le profil') }}</button></div>
      </form>
    </section>

    <section class="panel profile-settings-card">
      <div class="panel-heading"><div><span class="eyebrow">{{ t('MON COMMERCE') }}</span><h2>{{ t('Paramètres du commerce') }}</h2></div></div>
      <form class="modal-form profile-form" @submit.prevent="saveShopSettings">
        <label>{{ t('Devise') }}<select v-model="shopSettings.currency" :disabled="!canEditShop || !isOnline">
          <option value="XOF">{{ t('XOF — Franc CFA (BCEAO)') }}</option>
          <option value="XAF">{{ t('XAF — Franc CFA (BEAC)') }}</option>
          <option value="EUR">{{ t('EUR — Euro') }}</option>
          <option value="USD">{{ t('USD — Dollar américain') }}</option>
        </select></label>
        <label>{{ t('Seuil par défaut des nouveaux produits') }}<input v-model="shopSettings.default_min_stock" type="number" min="0" step="0.001" :disabled="!canEditShop || !isOnline" /></label>
        <p class="form-hint">{{ t('Ce seuil ne s’applique qu’aux nouveaux produits; les seuils existants restent inchangés.') }}</p>
        <p v-if="!canEditShop" class="form-hint">{{ t('Seul le propriétaire peut modifier les paramètres du commerce.') }}</p>
        <div class="modal-actions"><span></span><button class="button primary" type="submit" :disabled="shopPending || !canEditShop || !isOnline"><LoaderCircle v-if="shopPending" class="spin" :size="16" /><Save v-else :size="16" />{{ t('Enregistrer les paramètres') }}</button></div>
      </form>
    </section>
  </div>
</template>
