const axios = require('axios');
const fs = require('fs');
const path = require('path');
const puppeteer = require('puppeteer-core'); // Berubah ke puppeteer-core
const { state } = require('./helpers/state'); 

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
try { COUNTRY_EMOJI = require('./country.json'); } catch (e) {}

const getCountryEmoji = (name) => (name ? (COUNTRY_EMOJI[name.toUpperCase()] || "🏴‍☠️") : "🏴‍☠️");
const cleanPhoneNumber = (p) => (p ? p.replace(/[^0-9X]/g, '') : "N/A");
const cleanServiceName = (s) => {
    if (!s) return "Unknown";
    const low = s.toLowerCase();
    return low.includes('facebook') ? 'Facebook' : low.includes('whatsapp') ? 'WhatsApp' : s.trim();
};

const formatLiveMessage = (rangeVal, count, country, service, msg) => {
    const emoji = getCountryEmoji(country);
    const header = count > 1 ? `<code>${rangeVal}</code> (${count}x)` : `<code>${rangeVal}</code>`;
    const escaped = msg.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
    return `🌤️<b>Live message new range</b>\n\n☎️Range    : ${header}\n${emoji} Country : ${country}\n📪 Service : ${service}\n\n🗯️Message Available :\n<blockquote>${escaped}</blockquote>`;
};

// --- LOGIKA KONEK PUPPETEER ---
async function getSharedPage() {
    try {
        const wsAddr = process.env.WS_ENDPOINT || state.wsEndpoint;
        if (!wsAddr) return null;

        const browser = await puppeteer.connect({ browserWSEndpoint: wsAddr });
        const page = await browser.newPage();
        
        // Set User Agent agar konsisten dengan main process
        await page.setUserAgent('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36');
        
        console.log("📍 [RANGE] Berhasil buka Tab Baru Puppeteer untuk Console.");
        return page;
    } catch (e) {
        console.error("❌ [RANGE] Gagal buka tab:", e.message);
        return null;
    }
}

async function monitorTask() {
    console.log("🚀 [RANGE] Service Background Active (Wait for Browser...)");
    
    while (!(process.env.WS_ENDPOINT || state.wsEndpoint)) {
        await new Promise(r => setTimeout(r, 2000));
    }

    console.log("✅ [RANGE] Browser Linked. Monitoring Tab Console...");
    let page = null;

    while (true) {
        try {
            if (!page || page.isClosed()) {
                page = await getSharedPage();
                if (!page) { await new Promise(r => setTimeout(r, 5000)); continue; }
                
                // Blokir gambar untuk hemat kuota/performa
                await page.setRequestInterception(true);
                page.on('request', (req) => {
                    if (['image', 'font'].includes(req.resourceType())) req.abort();
                    else req.continue();
                });
            }

            if (!page.url().includes('/console')) {
                await page.goto(CONFIG.DASHBOARD_URL, { waitUntil: 'networkidle2', timeout: 60000 });
                console.log("📍 [RANGE] Navigasi ke Console sukses.");
            }

            const CONSOLE_SELECTOR = ".group.flex.flex-col.sm\\:flex-row.sm\\:items-start.gap-3.p-3.rounded-lg";
            await page.waitForSelector(CONSOLE_SELECTOR, { timeout: 15000 }).catch(() => {});
            
            // Ambil data menggunakan evaluate agar lebih cepat dan stabil di Puppeteer
            const dataItems = await page.evaluate((sel) => {
                const elements = document.querySelectorAll(sel);
                return Array.from(elements).map(el => {
                    const countryRaw = el.querySelector(".flex-shrink-0 .text-\\[10px\\].text-slate-600.mt-1.font-mono")?.innerText || "";
                    const serviceRaw = el.querySelector(".text-blue-400")?.innerText || "";
                    const phoneRaw = el.querySelector(".font-mono:last-of-type")?.innerText || "";
                    const msgRaw = el.querySelector("p")?.innerText || "";
                    return { countryRaw, serviceRaw, phoneRaw, msgRaw };
                });
            }, CONSOLE_SELECTOR);

            for (const item of dataItems) {
                try {
                    const country = item.countryRaw.includes("•") ? item.countryRaw.split("•")[1].trim() : "Unknown";
                    if (CONFIG.BANNED_COUNTRIES.includes(country.toLowerCase())) continue;

                    const service = cleanServiceName(item.serviceRaw);
                    if (!CONFIG.ALLOWED_SERVICES.some(s => service.toLowerCase().includes(s))) continue;

                    const phone = cleanPhoneNumber(item.phoneRaw);
                    const fullMessage = item.msgRaw.replace('➜', '').trim();

                    if (phone.includes('XXX')) {
                        const cacheKey = `${phone}_${fullMessage.slice(0, 15)}`; 
                        if (!CACHE_SET.has(cacheKey)) {
                            CACHE_SET.add(cacheKey);
                            const cur = SENT_MESSAGES.get(phone) || { count: 0 };
                            MESSAGE_QUEUE.push({ 
                                rangeVal: phone, country, service, count: cur.count + 1, 
                                text: formatLiveMessage(phone, cur.count + 1, country, service, fullMessage) 
                            });
                            
                            if (!IS_PROCESSING_QUEUE) processQueue();
                        }
                    }
                } catch (e) {}
            }
        } catch (err) { 
            console.error("❌ [RANGE] Loop Error:", err.message);
            page = null; 
        }
        await new Promise(r => setTimeout(r, 15000));
    }
}

async function processQueue() {
    IS_PROCESSING_QUEUE = true;
    while (MESSAGE_QUEUE.length > 0) {
        const item = MESSAGE_QUEUE.shift();
        try {
            await axios.post(`https://api.telegram.org/bot${CONFIG.BOT_TOKEN}/sendMessage`, {
                chat_id: CONFIG.CHAT_ID, text: item.text, parse_mode: 'HTML',
                reply_markup: { inline_keyboard: [[{ text: "📞 Get Number", url: "https://t.me/myzuraisgoodbot" }]] }
            });
            SENT_MESSAGES.set(item.rangeVal, { count: item.count, timestamp: Date.now() });
        } catch (e) {}
        await new Promise(r => setTimeout(r, CONFIG.SEND_DELAY));
    }
    IS_PROCESSING_QUEUE = false;
}

monitorTask();
