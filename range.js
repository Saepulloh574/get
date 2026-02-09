const axios = require('axios');
const fs = require('fs');
const path = require('path');
const { chromium } = require('playwright');

// Mengambil state global agar berbagi instance browser dengan main process
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

// ==================== GLOBAL VARIABLES ====================
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

// ==================== UTILITY ====================
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

// --- FUNGSI AMBIL PAGE (SUPPORT SHARED STATE & WS) ---
async function getSharedPage() {
    try {
        if (state && state.browser) {
            const contexts = state.browser.contexts();
            const context = contexts.length > 0 ? contexts[0] : await state.browser.newContext();
            return await context.newPage();
        } 
        else if (process.env.WS_ENDPOINT) {
            // Menggunakan connectOverCDP jika memungkinkan atau connect biasa
            const browser = await chromium.connect(process.env.WS_ENDPOINT);
            const context = browser.contexts()[0] || await browser.newContext();
            return await context.newPage();
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

// ==================== QUEUE SYSTEM ====================
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
                chat_id: CONFIG.CHAT_ID, 
                text: item.text, 
                parse_mode: 'HTML',
                reply_markup: { 
                    inline_keyboard: [[{ text: "📞 Get Number", url: "https://t.me/myzuraisgoodbot" }]] 
                }
            });

            if (res.data.ok) {
                SENT_MESSAGES.set(item.rangeVal, { 
                    message_id: res.data.result.message_id, 
                    count: item.count, 
                    timestamp: Date.now() 
                });
                saveToInlineJson(item.rangeVal, item.country, item.service);
            }
        } catch (e) { console.error("❌ [RANGE] TG Error"); }
        await new Promise(r => setTimeout(r, CONFIG.SEND_DELAY));
    }
    IS_PROCESSING_QUEUE = false;
}

// ==================== MONITOR LOGIC ====================
async function monitorTask() {
    console.log("🚀 [RANGE] Service Background Active (Shared Tab Mode).");

    const checkState = setInterval(async () => {
        if (state.browser || process.env.WS_ENDPOINT) {
            clearInterval(checkState);
            console.log("✅ [RANGE] Browser terdeteksi. Memulai monitoring Tab Console...");
            runMonitoringLoop();
        }
    }, 5000);

    async function runMonitoringLoop() {
        let page = null;
        while (true) {
            try {
                if (!page || page.isClosed()) {
                    page = await getSharedPage();
                    if (!page) {
                        await new Promise(r => setTimeout(r, 5000));
                        continue;
                    }
                    // Optimasi: Blokir gambar biar tab ini gak boros RAM
                    await page.route('**/*.{png,jpg,jpeg,gif,svg}', route => route.abort());
                }

                if (!page.url().includes('/console')) {
                    await page.goto(CONFIG.DASHBOARD_URL, { waitUntil: 'domcontentloaded', timeout: 60000 });
                }

                // Selector Dashboard Console StexSMS
                const CONSOLE_SELECTOR = ".group.flex.flex-col.sm\\:flex-row.sm\\:items-start.gap-3.p-3.rounded-lg";
                await page.waitForSelector(CONSOLE_SELECTOR, { timeout: 15000 }).catch(() => {});
                
                const elements = await page.locator(CONSOLE_SELECTOR).all();

                for (const el of elements) {
                    try {
                        const rawC = await el.locator(".flex-shrink-0 .text-\\[10px\\].text-slate-600.mt-1.font-mono").innerText();
                        const country = rawC.includes("•") ? rawC.split("•")[1].trim() : "Unknown";
                        if (CONFIG.BANNED_COUNTRIES.includes(country.toLowerCase())) continue;

                        const sRaw = await el.locator(".flex-grow.min-w-0 .text-xs.font-bold.text-blue-400").innerText();
                        const service = cleanServiceName(sRaw);
                        if (!CONFIG.ALLOWED_SERVICES.some(s => service.toLowerCase().includes(s))) continue;

                        const phoneRaw = await el.locator(".flex-grow.min-w-0 .text-\\[10px\\].font-mono").last().innerText();
                        const phone = cleanPhoneNumber(phoneRaw);
                        
                        const msgRaw = await el.locator(".flex-grow.min-w-0 p").innerText();
                        const fullMessage = msgRaw.replace('➜', '').trim();

                        if (phone.includes('XXX')) {
                            const cacheKey = `${phone}_${fullMessage.slice(0, 15)}`; 
                            if (!CACHE_SET.has(cacheKey)) {
                                CACHE_SET.add(cacheKey);
                                
                                if (CACHE_SET.size > 500) {
                                    const firstKey = CACHE_SET.values().next().value;
                                    CACHE_SET.delete(firstKey);
                                }

                                const cur = SENT_MESSAGES.get(phone) || { count: 0 };
                                const newCount = cur.count + 1;

                                MESSAGE_QUEUE.push({ 
                                    rangeVal: phone, 
                                    country, 
                                    service, 
                                    count: newCount, 
                                    text: formatLiveMessage(phone, newCount, country, service, fullMessage) 
                                });
                                processQueue();
                            }
                        }
                    } catch (e) { continue; }
                }

                // Cleanup data lama setiap loop
                const now = Date.now();
                for (let [r, v] of SENT_MESSAGES.entries()) {
                    if (now - v.timestamp > 1800000) SENT_MESSAGES.delete(r);
                }

            } catch (err) {
                console.error(`❌ [RANGE] Loop Error: ${err.message}`);
                if (page) await page.close().catch(() => {});
                page = null;
                await new Promise(r => setTimeout(r, 10000));
            }
            // Scan setiap 15 detik agar tidak membebani browser utama
            await new Promise(r => setTimeout(r, 15000));
        }
    }
}

monitorTask();
