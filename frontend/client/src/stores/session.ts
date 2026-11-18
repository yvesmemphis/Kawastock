import { computed, ref } from 'vue';
import { defineStore } from 'pinia';
import { get, post, setShop, setTokens } from '../api/http';
import { clearCachedResponses, clearQueuedOperations } from '../offline';

export interface Membership { shop_id: string; shop_name: string; role: string }
export interface User {
  id: string;
  email: string;
  username: string;
  first_name: string;
  last_name: string;
  memberships: Membership[];
  profile_photo_url: string | null;
  theme: 'light' | 'dark';
  language: 'fr' | 'en';
}
export interface Shop {
  id: string;
  name: string;
  my_role: string;
  currency: string;
  default_min_stock: string;
}

export const useSession = defineStore('session', () => {
  const user = ref<User | null>(null);
  const shops = ref<Shop[]>([]);
  const activeShopId = ref(sessionStorage.getItem('kawa.shop') || '');
  const loading = ref(false);
  const authenticated = computed(() => !!user.value);
  const shop = computed(() => shops.value.find(item => item.id === activeShopId.value) || null);
  const role = computed(() => shop.value?.my_role || user.value?.memberships.find(item => item.shop_id === activeShopId.value)?.role || '');

  async function loadProfile() {
    const profile = await get<User>('auth/me/');
    user.value = profile;
    const data = await get<Shop[] | { results: Shop[] }>('shops/');
    shops.value = Array.isArray(data) ? data : data.results || [];
    if (!shops.value.some(item => item.id === activeShopId.value)) {
      activeShopId.value = shops.value[0]?.id || '';
      setShop(activeShopId.value || null);
    }
    return profile;
  }
  async function login(email: string, password: string) {
    const pair = await post<{ access: string; refresh: string }>('auth/token/', { email, password });
    setTokens(pair.access, pair.refresh);
    await loadProfile();
  }
  async function register(payload: Record<string, string>) {
    await post('auth/register/', payload);
    await login(payload.email, payload.password);
  }
  async function restore() {
    if (!sessionStorage.getItem('kawa.access') && !sessionStorage.getItem('kawa.refresh')) return;
    loading.value = true;
    try { await loadProfile(); } catch { user.value = null; shops.value = []; setTokens(null, null); }
    finally { loading.value = false; }
  }
  function selectShop(id: string) { activeShopId.value = id; setShop(id); }
  async function logout() {
    setTokens(null, null);
    setShop(null);
    user.value = null;
    shops.value = [];
    activeShopId.value = '';
    try {
      await clearCachedResponses();
      await clearQueuedOperations();
    } catch (error) {
      console.warn('Unable to clear cached KawaStock data on logout.', error);
    }
  }
  return { user, shops, activeShopId, loading, authenticated, shop, role, login, register, restore, selectShop, logout, loadProfile };
});
