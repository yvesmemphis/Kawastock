<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { useSession } from './stores/session';
import { Boxes, ChartNoAxesCombined, ChevronDown, ClipboardList, LayoutDashboard, LogOut, Menu, Package, ShoppingBag, Store, Truck, Users, X } from '@lucide/vue';
import { post } from './api/http';
import { translate, useI18n } from './i18n';
import { isOnline } from './offline';

const session = useSession();
const { t } = useI18n();
const route = useRoute();
const router = useRouter();
const menuOpen = ref(false);
const shopMenuOpen = ref(false);
const creatingShop = ref(false);
const shopName = ref('');
const shopError = ref('');
const isLogin = computed(() => route.name === 'login');
const canDashboard = computed(() => ['owner','manager','viewer'].includes(session.role));
const nav = computed(() => [
  { label: t('Vue d’ensemble'), path: '/', icon: LayoutDashboard, roles: ['owner','manager','viewer'] },
  { label: t('Produits'), path: '/produits', icon: Package, roles: ['owner','manager','stock_manager','seller','viewer'] },
  { label: t('Catégories'), path: '/categories', icon: Boxes, roles: ['owner','manager','stock_manager','seller','viewer'] },
  { label: t('Inventaire'), path: '/stock', icon: Boxes, roles: ['owner','manager','stock_manager','viewer'] },
  { label: t('Ventes & caisse'), path: '/ventes', icon: ShoppingBag, roles: ['owner','manager','seller','viewer'] },
  { label: t('Achats'), path: '/achats', icon: ClipboardList, roles: ['owner','manager','stock_manager','viewer'] },
  { label: t('Fournisseurs'), path: '/fournisseurs', icon: Truck, roles: ['owner','manager','stock_manager','viewer'] },
  { label: t('Équipe'), path: '/equipe', icon: Users, roles: ['owner','manager'] },
  { label: t('Rapports'), path: '/rapports', icon: ChartNoAxesCombined, roles: ['owner','manager','viewer'] },
].filter(item => item.roles.includes(session.role)));
const roleLabels: Record<string,string> = { owner: t('Propriétaire'), manager: t('Gérant·e'), stock_manager: t('Gestion de stock'), seller: t('Vendeur·se'), viewer: t('Lecture seule') };
const initials = computed(() => (session.user?.first_name || session.user?.username || session.user?.email || 'K').slice(0,1).toUpperCase());
watch(() => session.user?.language, language => {
  document.title = `${translate(language || 'fr', String(route.meta.title || 'Gestion'))} · KawaStock`;
});

onMounted(async () => { if (!session.user && sessionStorage.getItem('kawa.access')) await session.restore(); });
watch(() => session.role, role => {
  if (!role) return;
  if (route.path === '/' && !['owner','manager','viewer'].includes(role)) router.replace(role === 'seller' ? '/ventes' : '/produits');
  if (route.path === '/equipe' && !['owner','manager'].includes(role)) router.replace('/');
  if (route.path === '/rapports' && !['owner','manager','viewer'].includes(role)) router.replace('/');
});
watch(isOnline, online => {
  const offlinePages = ['dashboard', 'products', 'categories', 'stock', 'sales', 'purchases', 'suppliers', 'reports', 'team', 'profile'];
  if (!online && route.name && !offlinePages.includes(String(route.name))) {
    router.replace(['owner', 'manager', 'viewer'].includes(session.role) ? '/' : '/produits');
  }
});
function changeShop(event: Event) { const id = (event.target as HTMLSelectElement).value; session.selectShop(id); shopMenuOpen.value = false; }
async function createShop() {
  shopError.value = '';
  if (shopName.value.trim().length < 2) { shopError.value = 'Saisissez un nom de commerce.'; return; }
  creatingShop.value = true;
  try { await post('shops/', { name: shopName.value.trim(), currency: 'XOF', timezone: 'Africa/Abidjan' }); await session.loadProfile(); router.push('/'); }
  catch (error) { shopError.value = error instanceof Error ? error.message : 'Création impossible.'; }
  finally { creatingShop.value = false; }
}
async function signOut() { await session.logout(); router.push('/connexion'); }
</script>

<template>
  <RouterView v-if="isLogin" />
  <div v-else-if="session.loading" class="app-loading"><span class="spinner"></span><span>{{ t('Ouverture de votre espace…') }}</span></div>
  <main v-else-if="session.authenticated && !session.shops.length" class="onboarding-page">
    <section class="onboarding-card"><div class="brand-mark large"><span></span><span></span><span></span></div><p class="eyebrow">{{ t('VOTRE ESPACE KAWASTOCK') }}</p><h1>{{ t('Commençons par votre commerce.') }}</h1><p class="muted">{{ t('Créez votre premier espace pour organiser vos produits, vos ventes et vos stocks.') }}</p><form @submit.prevent="createShop"><label>{{ t('Nom du commerce') }}<input v-model="shopName" :placeholder="t('Ex. Quincaillerie du Centre')" required /></label><p v-if="shopError" class="form-error">{{ t(shopError) }}</p><button class="button primary wide" :disabled="creatingShop || !isOnline">{{ creatingShop ? t('Création…') : t('Créer mon commerce') }}</button></form><button class="text-button" @click="signOut">{{ t('Se déconnecter') }}</button></section>
  </main>
  <div v-else-if="session.authenticated" class="app-shell" :class="{ 'theme-dark': session.user?.theme === 'dark' }">
    <div v-if="menuOpen" class="mobile-scrim" @click="menuOpen = false"></div>
    <aside class="sidebar" :class="{ 'sidebar-open': menuOpen }">
      <div class="brand"><div class="brand-mark"><span></span><span></span><span></span></div><span class="brand-name">kawa<span>stock</span></span><button class="icon-button sidebar-close" aria-label="Fermer le menu" @click="menuOpen = false"><X :size="18" /></button></div>
      <div class="workspace-chip"><div class="shop-avatar"><Store :size="17" /></div><div class="workspace-info"><span class="workspace-label">{{ t('ESPACE DE TRAVAIL') }}</span><strong>{{ session.shop?.name || t('Mon commerce') }}</strong></div><button class="icon-button shop-switch" :aria-label="t('Changer de commerce')" @click="shopMenuOpen = !shopMenuOpen"><ChevronDown :size="16" /></button>
        <div v-if="shopMenuOpen" class="shop-dropdown"><button v-for="shop in session.shops" :key="shop.id" @click="session.selectShop(shop.id); shopMenuOpen = false"><span>{{ shop.name }}</span><span v-if="shop.id === session.activeShopId">✓</span></button></div>
      </div>
      <nav class="side-nav"><span class="nav-caption">{{ t('GESTION') }}</span><RouterLink v-for="item in nav" :key="item.path" :to="item.path" class="nav-link" :class="{ active: route.path === item.path }" @click="menuOpen = false"><component :is="item.icon" :size="18" :stroke-width="1.8" /><span>{{ item.label }}</span><span v-if="item.path === '/stock'" class="nav-dot"></span></RouterLink></nav>
      <div class="sidebar-bottom"><div class="help-card"><div class="help-orbit">?</div><strong>{{ t('Besoin d’un coup de main ?') }}</strong><span>{{ t('Votre gestion, sans prise de tête.') }}</span></div><RouterLink to="/profil" class="user-card"><div class="user-avatar"><img v-if="session.user?.profile_photo_url" :src="session.user.profile_photo_url" alt="" /><span v-else>{{ initials }}</span></div><div class="user-details"><strong>{{ session.user?.first_name || session.user?.username }}</strong><span>{{ t('Profil et paramètres') }}</span></div></RouterLink></div>
    </aside>
    <section class="main-column"><header class="topbar"><button class="icon-button mobile-menu" aria-label="Ouvrir le menu" @click="menuOpen = true"><Menu :size="20" /></button><div class="breadcrumb"><span>KawaStock</span><span class="crumb-slash">/</span><strong>{{ t(String(route.meta.title || 'Gestion')) }}</strong></div><div class="topbar-right"><div class="online-status"><span></span> {{ t('En direct') }}</div><div class="topbar-divider"></div><RouterLink to="/profil" class="profile-mini"><span class="user-avatar small"><img v-if="session.user?.profile_photo_url" :src="session.user.profile_photo_url" alt="" /><span v-else>{{ initials }}</span></span><span>{{ session.user?.first_name || session.user?.username }}</span><ChevronDown :size="15" /></RouterLink><button class="icon-button logout-button" :aria-label="t('Se déconnecter')" :title="t('Se déconnecter')" @click="signOut"><LogOut :size="17" /></button></div></header>
      <div class="content-wrap"><div v-if="!isOnline" class="offline-banner" role="status">{{ t('Hors ligne : les opérations sélectionnées seront synchronisées au retour du réseau.') }}</div><div v-if="!session.activeShopId" class="notice notice-warning">{{ t('Sélectionnez un commerce pour afficher ses données.') }}</div><RouterView v-else /></div>
    </section>
  </div>
  <RouterView v-else />
</template>
