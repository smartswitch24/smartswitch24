// ─── Central Affiliate Widget & Offer Configuration ──────────────────────────
// Edit widget codes and affiliate URLs here.
// Pages import from this file — no page files need editing when you update a widget.

// ── Types ─────────────────────────────────────────────────────────────────────

export interface WidgetConfig {
  providerName: string;
  htmlCode: string;
  titleDe: string;
  titleAr: string;
  descriptionDe: string;
  descriptionAr: string;
  disclaimerDe: string;
  disclaimerAr: string;
}

export interface GeneralOffer {
  providerName: string;
  providerLogo: string;
  price: string;
  descriptionDe: string;
  descriptionAr: string;
  affiliateUrl: string;
  ctaDe: string;
  ctaAr: string;
  lastUpdated: string;
}

export interface TravelOffer {
  destination: string;
  hotelName: string;
  duration: string;
  departureAirport: string;
  price: string;
  provider: string;
  affiliateUrl: string;
  ctaDe: string;
  ctaAr: string;
  lastUpdated: string;
}

export interface FinanceOffer {
  providerName: string;
  providerLogo: string;
  productName: string;
  monthlyCost: string;
  bonusOrInterest: string;
  benefitsDe: string[];
  benefitsAr: string[];
  affiliateUrl: string;
  ctaDe: string;
  ctaAr: string;
  lastUpdated: string;
}

// ── Calculator Widgets ────────────────────────────────────────────────────────
// To activate: paste the provider's HTML/script into htmlCode.
// To deactivate: set htmlCode to '' — CalculatorEmbed falls back to placeholder mode.

export const stromCalculator: WidgetConfig = {
  providerName: 'CHECK24',
  // ↓ CHECK24 power widget — widget ID 864696 — verified working
  htmlCode: `<div style="width:100%" id="c24pp-power-iframe" data-scrollto="begin"></div>
    <script src="https://files.check24.net/widgets/auto/864696/c24pp-power-iframe/power-iframe.js"><\/script>`,
  titleDe: 'Jetzt Stromtarife vergleichen',
  titleAr: 'قارن أسعار الكهرباء الآن',
  descriptionDe: 'Kostenloser Vergleich – keine Anmeldung erforderlich. Wir können keine bestimmten Einsparungen garantieren.',
  descriptionAr: 'مقارنة مجانية – لا حاجة للتسجيل. لا يمكننا ضمان توفير مبالغ محددة.',
  disclaimerDe: 'Diese Seite enthält Partnerlinks zu CHECK24. Bei Vertragsabschluss über unsere Links erhalten wir ggf. eine Vergütung. Für Sie entstehen keine Mehrkosten.',
  disclaimerAr: 'يحتوي هذا الموقع على روابط شركاء لـ CHECK24. عند إبرام عقد عبر روابطنا قد نحصل على عمولة دون أي تكلفة إضافية عليك.',
};

export const gasCalculator: WidgetConfig = {
  providerName: 'CHECK24',
  // ↓ CHECK24 gas widget — widget ID 864696 — verified working
  htmlCode: `<div style="width:100%" id="c24pp-gas-iframe" data-scrollto="begin"></div>
    <script src="https://files.check24.net/widgets/auto/864696/c24pp-gas-iframe/gas-iframe.js"><\/script>`,
  titleDe: 'Jetzt Gastarife vergleichen',
  titleAr: 'قارن أسعار الغاز الآن',
  descriptionDe: 'Kostenloser Vergleich – keine Anmeldung erforderlich. Wir können keine bestimmten Einsparungen garantieren.',
  descriptionAr: 'مقارنة مجانية – لا حاجة للتسجيل. لا يمكننا ضمان توفير مبالغ محددة.',
  disclaimerDe: 'Diese Seite enthält Partnerlinks zu CHECK24. Bei Vertragsabschluss über unsere Links erhalten wir ggf. eine Vergütung. Für Sie entstehen keine Mehrkosten.',
  disclaimerAr: 'يحتوي هذا الموقع على روابط شركاء لـ CHECK24. عند إبرام عقد عبر روابطنا قد نحصل على عمولة دون أي تكلفة إضافية عليك.',
};

export const pauschalreisenWidget: WidgetConfig = {
  providerName: '',
  // ↓ PASTE YOUR TRAVEL AFFILIATE WIDGET CODE HERE
  htmlCode: '<div style="width: 100%" id="c24pp-package-iframe" data-offer="allgemein" data-scrollto="begin" data-forward-url="no"></div><script src="https://files.check24.net/widgets/auto/864696/c24pp-package-iframe/package-iframe.js"></script>',
  titleDe: 'Pauschalreisen vergleichen',
  titleAr: 'قارن رحلات السفر',
  descriptionDe: 'Vergleichen Sie Reiseangebote von führenden Veranstaltern.',
  descriptionAr: 'قارن عروض السفر من كبار منظمي الرحلات.',
  disclaimerDe: 'Einige Links auf dieser Seite sind Affiliate-Links. Bei Buchung über unsere Links erhalten wir ggf. eine Provision. Für Sie entstehen keine Mehrkosten.',
  disclaimerAr: 'بعض الروابط في هذه الصفحة هي روابط تسويق بالعمولة. عند الحجز عبر روابطنا قد نحصل على عمولة دون أي تكلفة إضافية عليك.',
};

export const finanzenWidget: WidgetConfig = {
  providerName: '',
  // ↓ PASTE YOUR FINANCE OVERVIEW WIDGET CODE HERE
  htmlCode: '',
  titleDe: 'Finanzprodukte vergleichen',
  titleAr: 'قارن المنتجات المالية',
  descriptionDe: 'Girokonten, Kreditkarten, Tagesgeld und Depot auf einen Blick.',
  descriptionAr: 'الحسابات الجارية وبطاقات الائتمان وحسابات التوفير والمحافظ الاستثمارية في لمحة واحدة.',
  disclaimerDe: 'Die Inhalte auf SmartSwitch24 dienen ausschließlich allgemeinen Informationszwecken und stellen keine Finanzberatung dar.',
  disclaimerAr: 'المحتوى على SmartSwitch24 هو لأغراض معلوماتية عامة فقط ولا يُعتبر استشارة مالية.',
};

export const girokontoWidget: WidgetConfig = {
  providerName: '<div style="width: 100%" id="tcpp-iframe-giro"></div><script src="https://form.partner-versicherung.de/widgets/181038/tcpp-iframe-giro/giro-iframe.js"></script>
',
  // ↓ PASTE YOUR GIROKONTO AFFILIATE WIDGET CODE HERE
  htmlCode: '',
  titleDe: 'Girokonto Vergleich',
  titleAr: 'مقارنة الحسابات الجارية',
  descriptionDe: 'Kostenlose Girokonten vergleichen und das beste Konto finden.',
  descriptionAr: 'قارن الحسابات الجارية المجانية وابحث عن أفضل حساب.',
  disclaimerDe: 'Die Inhalte auf SmartSwitch24 dienen ausschließlich allgemeinen Informationszwecken und stellen keine Finanzberatung dar.',
  disclaimerAr: 'المحتوى على SmartSwitch24 هو لأغراض معلوماتية عامة فقط ولا يُعتبر استشارة مالية.',
};

export const kreditkartenWidget: WidgetConfig = {
  providerName: '',
  // ↓ PASTE YOUR KREDITKARTEN AFFILIATE WIDGET CODE HERE
  htmlCode: '',
  titleDe: 'Kreditkarten Vergleich',
  titleAr: 'مقارنة بطاقات الائتمان',
  descriptionDe: 'Kreditkarten mit Cashback, Reiseversicherung und ohne Jahresgebühr vergleichen.',
  descriptionAr: 'قارن بطاقات الائتمان مع استرداد النقود وتأمين السفر وبدون رسوم سنوية.',
  disclaimerDe: 'Die Inhalte auf SmartSwitch24 dienen ausschließlich allgemeinen Informationszwecken und stellen keine Finanzberatung dar.',
  disclaimerAr: 'المحتوى على SmartSwitch24 هو لأغراض معلوماتية عامة فقط ولا يُعتبر استشارة مالية.',
};

export const tagesgeldWidget: WidgetConfig = {
  providerName: '',
  // ↓ PASTE YOUR TAGESGELD AFFILIATE WIDGET CODE HERE
  htmlCode: '',
  titleDe: 'Tagesgeld Vergleich',
  titleAr: 'مقارنة حسابات التوفير',
  descriptionDe: 'Tagesgeldkonten mit den höchsten Zinsen vergleichen.',
  descriptionAr: 'قارن حسابات التوفير ذات أعلى الفوائد.',
  disclaimerDe: 'Die Inhalte auf SmartSwitch24 dienen ausschließlich allgemeinen Informationszwecken und stellen keine Finanzberatung dar.',
  disclaimerAr: 'المحتوى على SmartSwitch24 هو لأغراض معلوماتية عامة فقط ولا يُعتبر استشارة مالية.',
};

export const depotWidget: WidgetConfig = {
  providerName: '',
  // ↓ PASTE YOUR DEPOT/BROKER AFFILIATE WIDGET CODE HERE
  htmlCode: '',
  titleDe: 'Depot Vergleich',
  titleAr: 'مقارنة محافظ الأوراق المالية',
  descriptionDe: 'Online-Depots und Broker vergleichen. Aktien, ETFs und Fonds günstig handeln.',
  descriptionAr: 'قارن محافظ الأوراق المالية عبر الإنترنت والوسطاء.',
  disclaimerDe: 'Die Inhalte auf SmartSwitch24 dienen ausschließlich allgemeinen Informationszwecken und stellen keine Finanzberatung dar.',
  disclaimerAr: 'المحتوى على SmartSwitch24 هو لأغراض معلوماتية عامة فقط ولا يُعتبر استشارة مالية.',
};

// ── Offer Arrays ──────────────────────────────────────────────────────────────
// Add real offers here. Empty array = no cards rendered. No fake data included.

export const generalOffers: GeneralOffer[] = [
  // {
  //   providerName: '',
  //   providerLogo: '',          // e.g. '/logos/provider.svg'
  //   price: '',                 // e.g. 'ab 29,90 € / Monat'
  //   descriptionDe: '',
  //   descriptionAr: '',
  //   affiliateUrl: '',          // ← PASTE AFFILIATE URL HERE
  //   ctaDe: 'Angebot ansehen',
  //   ctaAr: 'عرض العرض',
  //   lastUpdated: '',
  // },
];

export const travelOffers: TravelOffer[] = [
  // {
  //   destination: '',           // e.g. 'Mallorca, Spanien'
  //   hotelName: '',
  //   duration: '',              // e.g. '7 Nächte'
  //   departureAirport: '',      // e.g. 'Stuttgart (STR)'
  //   price: '',                 // e.g. 'ab 699 €'
  //   provider: '',
  //   affiliateUrl: '',          // ← PASTE AFFILIATE URL HERE
  //   ctaDe: 'Reise buchen',
  //   ctaAr: 'احجز الرحلة',
  //   lastUpdated: '',
  // },
];

export const financeOffers: FinanceOffer[] = [
  // {
  //   providerName: '',
  //   providerLogo: '',
  //   productName: '',           // e.g. 'DKB-Girokonto'
  //   monthlyCost: '',           // e.g. '0 € / Monat'
  //   bonusOrInterest: '',       // e.g. '50 € Startbonus' or '3,5 % p.a.'
  //   benefitsDe: [],
  //   benefitsAr: [],
  //   affiliateUrl: '',          // ← PASTE AFFILIATE URL HERE
  //   ctaDe: 'Konto eröffnen',
  //   ctaAr: 'افتح حساباً',
  //   lastUpdated: '',
  // },
];
