const axios = require('axios');
const fs = require('fs');
const path = require('path');
const { chromium } = require('playwright');
const { state } = require('./helpers/state'); 

// ==================== KONFIGURASI ====================
const CONFIG = {
    BOT_TOKEN: "8264103317:AAG_-LZQIxrMDIlLlttWQqIvA9xu_GNMwnc",
    CHAT_ID: "-1003358198353",
    DASHBOARD_URL: "https://stexsms.com/mdashboard/console",
    ALLOWED_SERVICES: ['whatsapp', 'facebook'],
    BANNED_COUNTRIES: ['angola'],
    SEND_DELAY: 2000 
};

let SENT_MESSAGES = new Map();
let CACHE_SET = new Set();
let MESSAGE_QUEUE = []; 
let IS_PROCESSING_QUEUE = false; 

let COUNTRY_EMOJI = {};
try {
    COUNTRY_EMOJI = require('./country.json');
} catch (e) {
    console.error("⚠️ [RANGE] country.json missing.");
}

const INLINE_JSON_PATH = path.join(__dirname, 'inline.json');

const getCountryEmoji = (name) => (name ? (COUNTRY_EMOJI[name.toUpperCase()] || "🏴‍☠️") : "🏴‍☠️");
const cleanPhoneNumber = (p) => (p ? p.replace(/[^0-9X]/g, '') : "N/A");
const cleanServiceName = (s) => {
    if (!s) return "Unknown";
    const low = s.toLowerCase();
    if (low.includes('facebook')) return 'Facebook';
    if (low.includes('whatsapp')) return 'WhatsApp';
    return s.trim();
};

const formatLiveMessage = (rangeVal, count, country, service, msg) => {
    const emoji = getCountryEmoji(country);
    const header = count > 1 ? `<code>${rangeVal}</code> (${count}x)` : `<code>${rangeVal}</code>`;
    const escaped = msg.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");

    return `🌤️<b>Live message new range</b>\n\n` +
           `☎️Range    : ${header}\n` +
           `${emoji} Country : ${country}\n` +
           `📪 Service : ${service}\n\n` +
           `🗯️Message Available :\n` +
           `<blockquote>${escaped}</blockquote>`;
};

// --- FIX LOGIKA KONEK: PAKSA NUMPANG TAB ---
async function getSharedPage() {
    try {
        const wsAddr = process.env.WS_ENDPOINT || state.wsEndpoint;
        if (wsAddr) {
            const browser = await chromium.connect(wsAddr);
            // KUNCI: Pakai contexts()[0] agar nempel di jendela lama
            const contexts = browser.contexts();
            if (contexts.length > 0) return await contexts[0].newPage();
            return null;
        } 
        else if (state && state.browser) {
            const contexts = state.browser.contexts();
            if (contexts.length > 0) return await contexts[0].newPage();
            return null;
        } 
        else {
            console.error("❌ [RANGE] Tidak ada browser instance yang tersedia.");
            return null;
        }
    } catch (e) {
        console.error("❌ [RANGE] Gagal mendapatkan Page:", e.message);
        return null;
    }
}

const saveToInlineJson = (rangeVal, country, service) => {
    const sMap = { 'whatsapp': 'WA', 'facebook': 'FB' };
    const shortS = sMap[service.toLowerCase()] || service.substring(0, 5).toUpperCase();
    try {
        let list = [];
        if (fs.existsSync(INLINE_JSON_PATH)) {
            const content = fs.readFileSync(INLINE_JSON_PATH, 'utf-8');
            list = content ? JSON.parse(content) : [];
        }
        if (list.some(i => i.range === rangeVal)) return;
        list.push({ range: rangeVal, country: country.toUpperCase(), emoji: getCountryEmoji(country), service: shortS });
        if (list.length > 20) list = list.slice(-20);
        fs.writeFileSync(INLINE_JSON_PATH, JSON.stringify(list, null, 2));
    } catch (e) { console.error("❌ [RANGE] Save Inline Error"); }
};

async function processQueue() {
    if (IS_PROCESSING_QUEUE || MESSAGE_QUEUE.length === 0) return;
    IS_PROCESSING_QUEUE = true;
    while (MESSAGE_QUEUE.length > 0) {
        const item = MESSAGE_QUEUE.shift();
        try {
            if (SENT_MESSAGES.has(item.rangeVal)) {
                const old = SENT_MESSAGES.get(item.rangeVal);
                await axios.post(`https://api.telegram.org/bot${CONFIG.BOT_TOKEN}/deleteMessage`, {
                    chat_id: CONFIG.CHAT_ID, message_id: old.message_id
                }).catch(() => {});
            }

            const res = await axios.post(`https://api.telegram.org/bot${CONFIG.BOT_TOKEN}/sendMessage`, {
                chat_id: CONFIG.CHAT_ID, text: item.text, parse_mode: 'HTML',
                reply_markup: { inline_keyboard: [[{ text: "📞 Get Number", url: "https://t.me/myzuraisgoodbot" }]] }
            });

            if (res.data.ok) {
                SENT_MESSAGES.set(item.rangeVal, { message_id: res.data.result.message_id, count: item.count, timestamp: Date.now() });
                saveToInlineJson(item.rangeVal, item.country, item.service);
            }
        } catch (e) {}
        await new Promise(r => setTimeout(r, CONFIG.SEND_DELAY));
    }
    IS_PROCESSING_QUEUE = false;
}

async function monitorTask() {
    const checkState = setInterval(() => {
        if (state.browser || process.env.WS_ENDPOINT) {
            clearInterval(checkState);
            runMonitoringLoop();
        }
    }, 5000);

    async function runMonitoringLoop() {
        let page = null;
        while (true) {
            try {
                if (!page || page.isClosed()) {
                    page = await getSharedPage();
                    if (!page) { await new Promise(r => setTimeout(r, 5000)); continue; }
                    await page.route('**/*.{png,jpg,jpeg,gif,svg}', r => r.abort());
                }
                if (!page.url().includes('/console')) await page.goto(CONFIG.DASHBOARD_URL, { waitUntil: 'domcontentloaded' });

                const CONSOLE_SELECTOR = ".group.flex.flex-col.sm\\:flex-row.sm\\:items-start.gap-3.p-3.rounded-lg";
                await page.waitForSelector(CONSOLE_SELECTOR, { timeout: 15000 }).catch(() => {});
                const elements = await page.locator(CONSOLE_SELECTOR).all();

                for (const el of elements) {
                    try {
                        const rawC = await el.locator(".flex-shrink-0 .text-\\[10px\\].text-slate-600.mt-1.font-mono").innerText();
                        const country = rawC.includes("•") ? rawC.split("•")[1].trim() : "Unknown";
                        if (CONFIG.BANNED_COUNTRIES.includes(country.toLowerCase())) continue;

                        const service = cleanServiceName(await el.locator(".text-blue-400").innerText());
                        if (!CONFIG.ALLOWED_SERVICES.some(s => service.toLowerCase().includes(s))) continue;

                        const phone = cleanPhoneNumber(await el.locator(".font-mono").last().innerText());
                        const fullMessage = (await el.locator("p").innerText()).replace('➜', '').trim();

                        if (phone.includes('XXX')) {
                            const cacheKey = `${phone}_${fullMessage.slice(0, 15)}`; 
                            if (!CACHE_SET.has(cacheKey)) {
                                CACHE_SET.add(cacheKey);
                                const cur = SENT_MESSAGES.get(phone) || { count: 0 };
                                MESSAGE_QUEUE.push({ rangeVal: phone, country, service, count: cur.count + 1, text: formatLiveMessage(phone, cur.count + 1, country, service, fullMessage) });
                                processQueue();
                            }
                        }
                    } catch (e) {}
                }
            } catch (err) { if (page) await page.close().catch(() => {}); page = null; }
            await new Promise(r => setTimeout(r, 15000));
        }
    }
}
monitorTask();
