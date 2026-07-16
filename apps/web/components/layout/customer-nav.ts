import {
  Activity,
  Anchor,
  BarChart3,
  Coins,
  Crosshair,
  GitCompare,
  Layers,
  LayoutDashboard,
  LineChart,
  Link2,
  ListOrdered,
  Power,
  Receipt,
  Settings,
  SlidersHorizontal,
  TrendingUp,
  UserCircle,
  Zap,
  type LucideIcon,
} from "lucide-react";

export type CustomerNavItem = { href: string; label: string; icon: LucideIcon; shortLabel?: string };
export type CustomerNavSection = { title: string; items: CustomerNavItem[] };

export const CUSTOMER_NAV_SECTIONS: CustomerNavSection[] = [
  {
    title: "Genel",
    items: [
      { href: "/dashboard", label: "Panel", shortLabel: "Panel", icon: LayoutDashboard },
      { href: "/profil", label: "Hesap Profilim", icon: UserCircle },
    ],
  },
  {
    title: "Islem & Pozisyon",
    items: [
      { href: "/positions", label: "Pozisyonlar", shortLabel: "Pozisyon", icon: ListOrdered },
      { href: "/orders", label: "Emirler", shortLabel: "Emirler", icon: Receipt },
      { href: "/trades", label: "Islem Gecmisi", icon: Receipt },
      { href: "/olta", label: "Olta Emirleri", icon: Anchor },
      { href: "/olta-pozisyonlar", label: "Olta Pozisyonlar", icon: Anchor },
    ],
  },
  {
    title: "Strateji & Bot",
    items: [
      { href: "/avci", label: "Avci", icon: Crosshair },
      { href: "/signals", label: "Sinyaller & Analiz", shortLabel: "Sinyaller", icon: LineChart },
      { href: "/pozisyon-ayarlari", label: "Pozisyon Ayarlari", icon: SlidersHorizontal },
      { href: "/bot-control", label: "Bot Kontrol", shortLabel: "Bot", icon: Power },
    ],
  },
  {
    title: "Piyasa Analizi",
    items: [
      { href: "/market", label: "Market Piyasasi", icon: BarChart3 },
      { href: "/piyasa-nabzi", label: "Piyasa Nabzi", icon: Activity },
      { href: "/btc-impuls", label: "BTC Impuls", icon: Zap },
      { href: "/market-regime", label: "Piyasa Rejimi", icon: TrendingUp },
      { href: "/trade-candidates", label: "Aday Karsilastirma", icon: GitCompare },
      { href: "/coin-profiles", label: "Coin Profilleri", icon: Layers },
    ],
  },
  {
    title: "Sistem",
    items: [
      { href: "/symbols", label: "Semboller", icon: Coins },
      { href: "/binance", label: "Binance Baglantisi", icon: Link2 },
      { href: "/settings", label: "Ayarlar", icon: Settings },
    ],
  },
];

export const MOBILE_BOTTOM_NAV: CustomerNavItem[] = [
  { href: "/dashboard", label: "Panel", shortLabel: "Panel", icon: LayoutDashboard },
  { href: "/positions", label: "Pozisyonlar", shortLabel: "Pozisyon", icon: ListOrdered },
  { href: "/signals", label: "Sinyaller", shortLabel: "Sinyaller", icon: LineChart },
  { href: "/bot-control", label: "Bot Kontrol", shortLabel: "Bot", icon: Power },
];
