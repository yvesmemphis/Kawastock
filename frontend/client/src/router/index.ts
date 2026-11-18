import { createRouter, createWebHistory } from 'vue-router';
import { useSession } from '../stores/session';
import DashboardView from '../views/DashboardView.vue';
import LoginView from '../views/LoginView.vue';
import WorkspaceView from '../views/WorkspaceView.vue';
import ProfileView from '../views/ProfileView.vue';
import { translate } from '../i18n';
import { isOnline } from '../offline';

const reportRoles = ['owner', 'manager', 'viewer'];
const stockRoles = ['owner', 'manager', 'stock_manager', 'viewer'];
const allRoles = ['owner', 'manager', 'stock_manager', 'seller', 'viewer'];
export const routes = [
  { path: '/', name: 'dashboard', component: DashboardView, meta: { title: 'Vue d’ensemble', roles: reportRoles } },
  { path: '/produits', name: 'products', component: WorkspaceView, meta: { title: 'Produits', section: 'products', roles: allRoles } },
  { path: '/categories', name: 'categories', component: WorkspaceView, meta: { title: 'Catégories', section: 'categories', roles: allRoles } },
  { path: '/stock', name: 'stock', component: WorkspaceView, meta: { title: 'Inventaire', section: 'stock', roles: stockRoles } },
  { path: '/ventes', name: 'sales', component: WorkspaceView, meta: { title: 'Ventes & caisse', section: 'sales', roles: ['owner','manager','seller','viewer'] } },
  { path: '/achats', name: 'purchases', component: WorkspaceView, meta: { title: 'Achats', section: 'purchases', roles: stockRoles } },
  { path: '/fournisseurs', name: 'suppliers', component: WorkspaceView, meta: { title: 'Fournisseurs', section: 'suppliers', roles: stockRoles } },
  { path: '/equipe', name: 'team', component: WorkspaceView, meta: { title: 'Équipe', section: 'team', roles: ['owner','manager'] } },
  { path: '/rapports', name: 'reports', component: WorkspaceView, meta: { title: 'Rapports', section: 'reports', roles: reportRoles } },
  { path: '/profil', name: 'profile', component: ProfileView, meta: { title: 'Profil et paramètres' } },
  { path: '/connexion', name: 'login', component: LoginView, meta: { title: 'Connexion', public: true } },
];
const router = createRouter({ history: createWebHistory(), routes });
router.beforeEach(async to => {
  const session = useSession();
  if (!session.user && sessionStorage.getItem('kawa.access')) await session.restore();
  if (!to.meta.public && !session.authenticated) return { name: 'login' };
  if (to.name === 'login' && session.authenticated) return { name: 'dashboard' };
  if (session.authenticated && session.role && to.meta.roles && !to.meta.roles.includes(session.role)) {
    return session.role === 'seller' ? { name: 'sales' } : { name: 'products' };
  }
  const offlinePages = ['dashboard', 'products', 'categories', 'stock', 'sales', 'purchases', 'suppliers', 'reports', 'team', 'profile'];
  if (!isOnline.value && !offlinePages.includes(String(to.name))) {
    return ['owner', 'manager', 'viewer'].includes(session.role) ? { name: 'dashboard' } : { name: 'products' };
  }
});
router.afterEach(to => {
  const session = useSession();
  document.title = `${translate(session.user?.language || 'fr', String(to.meta.title || 'Gestion'))} · KawaStock`;
});
export default router;
