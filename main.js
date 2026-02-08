const fs = require('fs');
const path = require('path');
const axios = require('axios');
const cron = require('node-cron');
const dotenv = require('dotenv');
const { fork } = require('child_process');
const { Mutex } = require('async-mutex'); // Tambahkan kembali untuk antrian

// --- IMPORT SHARED BROWSER ---
const { initSharedBrowser, getNewPage, restartBrowser } = require('./browser-shared.js');

// Load Env
dotenv.config();

// Load Configs
const HEADLESS_CONFIG = require('./headless.js');
const GLOBAL_COUNTRY_EMOJI = require('./country.json');

// --- KONFIGURASI DAN VARIABEL GLOBAL ---
const BOT_TOKEN = process.env.BOT_TOKEN;
const API = `https://api.telegram.org/bot${BOT_TOKEN}`;
const GROUP_ID_1 = parseInt(process.env.GROUP_ID_1);
const GROUP_ID_2 = parseInt(process.env.GROUP_ID_2);
const ADMIN_ID = parseInt(process.env.ADMIN_ID);
const STEX_EMAIL = process.env.STEX_EMAIL;
const STEX_PASSWORD = process.env.STEX_PASSWORD;

if (!BOT_TOKEN || !GROUP_ID_1 || !GROUP_ID_2 || !ADMIN_ID || !STEX_EMAIL || !STEX_PASSWORD) {
    console.error("[FATAL] Variabel lingkungan .env belum lengkap.");
    process.exit(1);
}

const TARGET_URL = "https://stexsms.com/mdashboard/getnum"; 
const BOT_USERNAME_LINK = "https://t.me/myzuraisgoodbot";
const GROUP_LINK_1 = "https://t.me/+E5grTSLZvbpiMTI1";
const GROUP_LINK_2 = "https://t.me/zura14g";

const OTP_PRICE = 0.003500;
const MIN_WD_AMOUNT = 1.000000;

// Files
const USER_FILE = "user.json";
const CACHE_FILE = "cache.json";
const INLINE_RANGE_FILE = "inline.json";
const WAIT_FILE = "wait.json";
const AKSES_GET10_FILE = "aksesget10.json";
const PROFILE_FILE = "profile.json";

// --- STATE BARU UNTUK ANTRIAN & STANDBY PAGE ---
const queueMutex = new Mutex();
let activeQueueCount = 0;
let mainStandbyPage = null; // Tab tunggal yang standby terus

// Global State Sets/Maps
let waitingBroadcastInput = new Set();
let broadcastMessage = {};
let verifiedUsers = new Set();
let waitingAdminInput = new Set();
let manualRangeInput = new Set();
let get10RangeInput = new Set();
let waitingDanaInput = new Set();
let pendingMessage = {};
let lastUsedRange = {};

// Progress Bar Config
const MAX_BAR_LENGTH = 12;
const FILLED_CHAR = "█";
const EMPTY_CHAR = "░";

const STATUS_MAP = {
    0: "Menunggu antrian active..", // Diubah untuk konteks antrian
    1: "Mempersiapkan tab standby..",
    3: "Mengirim permintaan nomor baru go.",
    4: "Memulai pencarian di tabel data..",
    5: "Mencari nomor pada siklus satu run",
    8: "Mencoba ulang pada siklus dua wait",
    12: "Nomor ditemukan memproses data fin"
};

// ==============================================================================
// FUNGSI UTILITAS MANAJEMEN FILE
// ==============================================================================

function loadJson(filename, defaultVal = []) {
    if (fs.existsSync(filename)) {
        try { return JSON.parse(fs.readFileSync(filename, 'utf8')); } catch (e) { return defaultVal; }
    }
    return defaultVal;
}
function saveJson(filename, data) { fs.writeFileSync(filename, JSON.stringify(data, null, 2)); }
function loadUsers() { return new Set(loadJson(USER_FILE, [])); }
function saveUsers(userId) {
    const users = loadUsers();
    if (!users.has(userId)) { users.add(userId); saveJson(USER_FILE, Array.from(users)); }
}
function loadCache() { return loadJson(CACHE_FILE, []); }
function saveCache(entry) {
    const cache = loadCache();
    if (cache.length >= 1000) cache.shift();
    cache.push(entry);
    saveJson(CACHE_FILE, cache);
}
function normalizeNumber(number) {
    let norm = String(number).trim().replace(/[\s-]/g, "");
    if (!norm.startsWith('+') && /^\d+$/.test(norm)) norm = '+' + norm;
    return norm;
}
function isInCache(number) {
    const cache = loadCache();
    const norm = normalizeNumber(number);
    return cache.some(entry => normalizeNumber(entry.number) === norm);
}
function loadInlineRanges() { return loadJson(INLINE_RANGE_FILE, []); }
function saveInlineRanges(ranges) { saveJson(INLINE_RANGE_FILE, ranges); }
function loadAksesGet10() { return new Set(loadJson(AKSES_GET10_FILE, [])); }
function saveAksesGet10(userId) {
    const akses = loadAksesGet10();
    akses.add(parseInt(userId));
    saveJson(AKSES_GET10_FILE, Array.from(akses));
}
function hasGet10Access(userId) {
    if (userId === ADMIN_ID) return true;
    return loadAksesGet10().has(parseInt(userId));
}
function loadProfiles() { return loadJson(PROFILE_FILE, {}); }
function saveProfiles(data) { saveJson(PROFILE_FILE, data); }
function getUserProfile(userId, firstName = "User") {
    const profiles = loadProfiles();
    const strId = String(userId);
    const today = new Date().toISOString().split('T')[0];
    if (!profiles[strId]) {
        profiles[strId] = { name: firstName, dana: "Belum Diset", dana_an: "Belum Diset", balance: 0.000000, otp_semua: 0, otp_hari_ini: 0, last_active: today };
        saveProfiles(profiles);
    } else {
        if (profiles[strId].name !== firstName) { profiles[strId].name = firstName; saveProfiles(profiles); }
        if (profiles[strId].last_active !== today) { profiles[strId].otp_hari_ini = 0; profiles[strId].last_active = today; saveProfiles(profiles); }
    }
    return profiles[strId];
}
function updateUserDana(userId, danaNumber, danaName) {
    const profiles = loadProfiles();
    if (profiles[String(userId)]) {
        profiles[String(userId)].dana = danaNumber;
        profiles[String(userId)].dana_an = danaName;
        saveProfiles(profiles); return true;
    } return false;
}
function loadWaitList() { return loadJson(WAIT_FILE, []); }
function saveWaitList(data) { saveJson(WAIT_FILE, data); }
function addToWaitList(number, userId, username, firstName) {
    let waitList = loadWaitList();
    const norm = normalizeNumber(number);
    let identity = username ? `@${username.replace('@', '')}` : `<a href="tg://user?id=${userId}">${firstName}</a>`;
    waitList = waitList.filter(item => item.number !== norm);
    waitList.push({ number: norm, user_id: userId, username: identity, timestamp: Date.now() / 1000 });
    saveWaitList(waitList);
}
function getProgressMessage(currentStep, totalSteps, prefixRange, numCount) {
    const progressRatio = Math.min(currentStep / 12, 1.0);
    const filledCount = Math.ceil(progressRatio * MAX_BAR_LENGTH);
    const emptyCount = MAX_BAR_LENGTH - filledCount;
    const bar = FILLED_CHAR.repeat(filledCount) + EMPTY_CHAR.repeat(emptyCount);
    let status = STATUS_MAP[currentStep] || STATUS_MAP[0];
    return `<code>${status}</code>\n<blockquote>Range: <code>${prefixRange}</code> | Jumlah: <code>${numCount}</code></blockquote>\n<code>Load:</code> [${bar}]`;
}
function generateInlineKeyboard(ranges) {
    const keyboard = [];
    ranges.forEach(item => {
        const service = item.service || "WA";
        const text = `${item.emoji} ${item.country} ${service}`;
        const callbackData = `select_range:${item.range}`;
        keyboard.push([{ text: text, callback_data: callbackData }]);
    });
    keyboard.push([{ text: "INPUT MANUAL RANGE..🖊️", callback_data: "manual_range" }]);
    return { inline_keyboard: keyboard };
}

// ==============================================================================
// FUNGSI API TELEGRAM
// ==============================================================================

async function tgSend(chatId, text, replyMarkup = null) {
    const data = { chat_id: chatId, text: text, parse_mode: "HTML" };
    if (replyMarkup) data.reply_markup = replyMarkup;
    try { const res = await axios.post(`${API}/sendMessage`, data); if (res.data.ok) return res.data.result.message_id; } catch (e) { return null; }
    return null;
}
async function tgEdit(chatId, messageId, text, replyMarkup = null) {
    const data = { chat_id: chatId, message_id: messageId, text: text, parse_mode: "HTML" };
    if (replyMarkup) data.reply_markup = replyMarkup;
    try { await axios.post(`${API}/editMessageText`, data); } catch (e) { /* ignore */ }
}
async function tgDelete(chatId, messageId) {
    try { await axios.post(`${API}/deleteMessage`, { chat_id: chatId, message_id: messageId }); } catch (e) { /* ignore */ }
}
async function tgSendAction(chatId, action = "typing") {
    try { await axios.post(`${API}/sendChatAction`, { chat_id: chatId, action: action }); } catch (e) { /* ignore */ }
}
async function tgGetUpdates(offset) {
    try { const res = await axios.get(`${API}/getUpdates`, { params: { offset: offset, timeout: 5 } }); return res.data; } catch (e) { return { ok: false, result: [] }; }
}
async function isUserInGroup(userId, groupId) {
    try {
        const res = await axios.get(`${API}/getChatMember`, { params: { chat_id: groupId, user_id: userId } });
        if (!res.data.ok) return false;
        return ["member", "administrator", "creator"].includes(res.data.result.status);
    } catch (e) { return false; }
}
async function isUserInBothGroups(userId) {
    const [g1, g2] = await Promise.all([isUserInGroup(userId, GROUP_ID_1), isUserInGroup(userId, GROUP_ID_2)]);
    return g1 && g2;
}
async function tgBroadcast(messageText, adminId) {
    const userIds = Array.from(loadUsers());
    let success = 0, fail = 0;
    let adminMsgId = await tgSend(adminId, `🔄 Siaran ke **${userIds.length}** pengguna...`);
    for (let i = 0; i < userIds.length; i++) {
        const uid = userIds[i];
        if (i % 10 === 0 && adminMsgId) await tgEdit(adminId, adminMsgId, `🔄 Siaran: **${i}/${userIds.length}** (Sukses: ${success}, Gagal: ${fail})`);
        const res = await tgSend(uid, messageText);
        if (res) success++; else fail++;
        await new Promise(r => setTimeout(r, 50));
    }
    const report = `✅ Siaran Selesai!\n👥 Total: <b>${userIds.length}</b>\n🟢 Sukses: <b>${success}</b>\n🔴 Gagal: <b>${fail}</b>`;
    if (adminMsgId) await tgEdit(adminId, adminMsgId, report); else await tgSend(adminId, report);
}

// ==============================================================================
// BROWSER HELPERS
// ==============================================================================

async function getNumberAndCountryFromRow(rowSelector, page) {
    try {
        const row = page.locator(rowSelector);
        if (!(await row.isVisible())) return null;
        const phoneEl = row.locator("td:nth-child(1) span.font-mono");
        const numberRawList = await phoneEl.allInnerTexts();
        const numberRaw = numberRawList.length > 0 ? numberRawList[0].trim() : null;
        const number = numberRaw ? normalizeNumber(numberRaw) : null;
        if (!number || isInCache(number)) return null;
        const statusEl = row.locator("td:nth-child(1) div:nth-child(2) span");
        const statusTextList = await statusEl.allInnerTexts();
        const statusText = statusTextList.length > 0 ? statusTextList[0].trim().toLowerCase() : "unknown";
        if (statusText.includes("success") || statusText.includes("failed")) return null;
        const countryEl = row.locator("td:nth-child(2) span.text-slate-200");
        const countryList = await countryEl.allInnerTexts();
        const country = countryList.length > 0 ? countryList[0].trim().toUpperCase() : "UNKNOWN";
        if (number && number.length > 5) return { number, country, status: statusText };
        return null;
    } catch (e) { return null; }
}

async function getAllNumbersParallel(page, numToFetch) {
    const tasks = [];
    for (let i = 1; i <= numToFetch + 5; i++) {
        tasks.push(getNumberAndCountryFromRow(`tbody tr:nth-child(${i})`, page));
    }
    const results = await Promise.all(tasks);
    const currentNumbers = [];
    const seen = new Set();
    for (const res of results) {
        if (res && res.number && !seen.has(res.number)) {
            currentNumbers.push(res);
            seen.add(res.number);
        }
    }
    return currentNumbers;
}

// ==============================================================================
// LOGIC UTAMA (REFACTORED WITH QUEUE & STANDBY PAGE)
// ==============================================================================

async function processUserInput(userId, prefix, clickCount, usernameTg, firstNameTg, messageIdToEdit = null) {
    let msgId = messageIdToEdit || pendingMessage[userId];
    const numToFetch = clickCount;

    // --- MANAJEMEN ANTRIAN ---
    activeQueueCount++;
    if (activeQueueCount > 1) {
        const queuePos = activeQueueCount - 1;
        const queueText = `⏳ <b>Menunggu di antrian active {${queuePos}}</b>\nMohon tunggu, bot sedang melayani user lain..`;
        if (!msgId) {
            msgId = await tgSend(userId, queueText);
        } else {
            await tgEdit(userId, msgId, queueText);
        }
    } else {
        if (!msgId) {
            msgId = await tgSend(userId, getProgressMessage(0, 0, prefix, numToFetch));
        }
    }
    if (!msgId) { activeQueueCount--; return; }

    // Mulai Kunci Mutex (Satu user pada satu waktu)
    const release = await queueMutex.acquire();

    let actionInterval = null;
    try {
        // Jika antrian lebih dari 1, edit pesan saat giliran tiba
        if (activeQueueCount >= 1) {
            await tgEdit(userId, msgId, getProgressMessage(1, 0, prefix, numToFetch));
        }

        actionInterval = setInterval(() => { tgSendAction(userId, "typing"); }, 4500);
        
        // Pastikan Standby Page Siap & Di Halaman Yang Benar
        if (!mainStandbyPage || mainStandbyPage.isClosed()) {
            mainStandbyPage = await getNewPage();
            await mainStandbyPage.goto(TARGET_URL, { waitUntil: 'domcontentloaded' });
        } else {
            // Cek jika session logout atau halaman berubah, balikkan ke URL target
            if (mainStandbyPage.url() !== TARGET_URL) {
                await mainStandbyPage.goto(TARGET_URL, { waitUntil: 'domcontentloaded' });
            }
        }

        const page = mainStandbyPage;
        const startOpTime = Date.now() / 1000;

        const INPUT_SELECTOR = "input[name='numberrange']";
        await page.waitForSelector(INPUT_SELECTOR, { state: 'visible', timeout: 5000 });
        
        // Bersihkan & Isi Range
        await page.fill(INPUT_SELECTOR, "");
        await page.fill(INPUT_SELECTOR, prefix);
        
        let currentStep = 2; 
        const BUTTON_SELECTOR = "button:has-text('Get Number')";
        
        // Klik sesuai jumlah (Super Fast)
        for (let i = 0; i < clickCount; i++) {
            await page.click(BUTTON_SELECTOR, { force: true });
        }

        currentStep = 3; 
        await tgEdit(userId, msgId, getProgressMessage(currentStep, 0, prefix, numToFetch));

        // Delay sangat singkat karena tab sudah standby
        await new Promise(r => setTimeout(r, 1000));
        currentStep = 4;
        await tgEdit(userId, msgId, getProgressMessage(currentStep, 0, prefix, numToFetch));

        let foundNumbers = [];
        const startTime = Date.now() / 1000;
        
        // Loop pencarian cepat
        while ((Date.now() / 1000 - startTime) < 8.0) { // Timeout pencarian 8 detik
            foundNumbers = await getAllNumbersParallel(page, numToFetch);
            if (foundNumbers.length >= numToFetch) {
                currentStep = 12;
                break;
            }
            
            // Progress Update
            const elapsed = (Date.now() / 1000) - startOpTime;
            const targetStep = Math.min(11, Math.floor(elapsed * 1.5) + 4);
            if (targetStep > currentStep) {
                currentStep = targetStep;
                await tgEdit(userId, msgId, getProgressMessage(currentStep, 0, prefix, numToFetch));
            }
            await new Promise(r => setTimeout(r, 300));
        }

        if (!foundNumbers || foundNumbers.length === 0) {
            await tgEdit(userId, msgId, "❌ NOMOR TIDAK DI TEMUKAN. Coba lagi atau ganti range.");
            return;
        }

        const mainCountry = foundNumbers[0].country || "UNKNOWN";
        await tgEdit(userId, msgId, getProgressMessage(12, 0, prefix, numToFetch));

        // Save Data
        foundNumbers.forEach(entry => {
            saveCache({ number: entry.number, country: entry.country, user_id: userId, time: Date.now() });
            addToWaitList(entry.number, userId, usernameTg, firstNameTg);
        });

        lastUsedRange[userId] = prefix;
        const emoji = GLOBAL_COUNTRY_EMOJI[mainCountry] || "🗺️";
        
        let msg = (numToFetch === 10) ? "✅ The number is already.\n\n<code>" : "✅ The number is ready\n\n";
        if (numToFetch === 10) {
            foundNumbers.slice(0, 10).forEach(entry => msg += `${entry.number}\n`);
            msg += "</code>";
        } else {
            if (numToFetch === 1) {
                msg += `📞 Number  : <code>${foundNumbers[0].number}</code>\n`;
            } else {
                foundNumbers.slice(0, numToFetch).forEach((entry, idx) => {
                    msg += `📞 Number ${idx+1} : <code>${entry.number}</code>\n`;
                });
            }
            msg += `${emoji} COUNTRY : ${mainCountry}\n🏷️ Range   : <code>${prefix}</code>\n\n<b>🤖 Number available please use, Waiting for OTP</b>\n`;
        }

        const inlineKb = {
            inline_keyboard: [
                [{ text: "🔄 Change 1 Number", callback_data: `change_num:1:${prefix}` }],
                [{ text: "🔄 Change 3 Number", callback_data: `change_num:3:${prefix}` }],
                [{ text: "🔐 OTP Grup", url: GROUP_LINK_1 }, { text: "🌐 Change Range", callback_data: "getnum" }]
            ]
        };
        await tgEdit(userId, msgId, msg, inlineKb);

    } catch (e) {
        console.error(`[PROCESS ERROR User ${userId}]`, e);
        if (msgId) await tgEdit(userId, msgId, `❌ Error: ${e.message}`);
    } finally {
        if (actionInterval) clearInterval(actionInterval);
        activeQueueCount--; // Kurangi antrian
        release(); // Lepas kunci untuk user berikutnya
    }
}

// ==============================================================================
// TELEGRAM LOOP
// ==============================================================================

async function telegramLoop() {
    verifiedUsers = loadUsers();
    let offset = 0;
    await tgGetUpdates(-1);
    console.log("[TELEGRAM] Polling started...");

    while (true) {
        const data = await tgGetUpdates(offset);
        if (data && data.result) {
            for (const upd of data.result) {
                offset = upd.update_id + 1;
                
                // --- Tambahan Answer Callback agar tidak loading ---
                if (upd.callback_query) {
                    try { await axios.post(`${API}/answerCallbackQuery`, { callback_query_id: upd.callback_query.id }); } catch(e){}
                }

                if (upd.message) {
                    const msg = upd.message;
                    const chatId = msg.chat.id;
                    const userId = msg.from.id;
                    const firstName = msg.from.first_name || "User";
                    const usernameTg = msg.from.username;
                    const mention = usernameTg ? `@${usernameTg}` : `<a href='tg://user?id=${userId}'>${firstName}</a>`;
                    const text = msg.text || "";

                    if (userId === ADMIN_ID) {
                        if (text.startsWith("/add")) {
                            waitingAdminInput.add(userId);
                            const mid = await tgSend(userId, "Kirim range > country > service");
                            if (mid) pendingMessage[userId] = mid;
                            continue;
                        } else if (text === "/info") {
                            waitingBroadcastInput.add(userId);
                            const mid = await tgSend(userId, "Pesan siaran?");
                            if (mid) broadcastMessage[userId] = mid;
                            continue;
                        } else if (text.startsWith("/get10akses ")) {
                            const targetId = text.split(" ")[1];
                            saveAksesGet10(targetId);
                            await tgSend(userId, `✅ Akses get10 ok: ${targetId}`);
                            continue;
                        } else if (text === "/list") {
                            const profiles = loadProfiles();
                            let chunk = "LIST USER:\n";
                            for (const [uid, p] of Object.entries(profiles)) chunk += `${p.name} - $${(p.balance||0).toFixed(6)}\n`;
                            await tgSend(userId, chunk.substring(0, 4000));
                            continue;
                        }
                    }

                    if (text === "/get10") {
                        if (hasGet10Access(userId)) {
                            get10RangeInput.add(userId);
                            const mid = await tgSend(userId, "kirim range contoh 225071606XXX");
                            if (mid) pendingMessage[userId] = mid;
                        } else {
                            await tgSend(userId, "❌ No Access.");
                        }
                        continue;
                    }

                    if (waitingAdminInput.has(userId)) {
                        waitingAdminInput.delete(userId);
                        const newRanges = [];
                        const lines = text.trim().split('\n');
                        lines.forEach(line => {
                            if (line.includes(' > ')) {
                                const parts = line.split(' > ');
                                newRanges.push({ range: parts[0].trim(), country: parts[1].trim().toUpperCase(), emoji: GLOBAL_COUNTRY_EMOJI[parts[1].trim().toUpperCase()] || "🗺️", service: parts[2] ? parts[2].trim().toUpperCase() : "WA" });
                            }
                        });
                        const pMsgId = pendingMessage[userId];
                        delete pendingMessage[userId];
                        const current = loadInlineRanges();
                        current.push(...newRanges);
                        saveInlineRanges(current);
                        await tgEdit(userId, pMsgId, `✅ Saved ${newRanges.length} ranges.`);
                        continue;
                    }

                    if (waitingBroadcastInput.has(userId)) {
                        waitingBroadcastInput.delete(userId);
                        const pMsgId = broadcastMessage[userId];
                        delete broadcastMessage[userId];
                        if (text === ".batal") await tgEdit(chatId, pMsgId, "❌ Batal.");
                        else { await tgEdit(chatId, pMsgId, "✅ Siaran..."); await tgBroadcast(text, userId); }
                        continue;
                    }

                    if (waitingDanaInput.has(userId)) {
                        const lines = text.trim().split('\n');
                        if (lines.length >= 2 && /^[\d+]+$/.test(lines[0].trim())) {
                            waitingDanaInput.delete(userId);
                            updateUserDana(userId, lines[0].trim(), lines.slice(1).join(' ').trim());
                            await tgSend(userId, `✅ Dana Saved!`);
                        } else await tgSend(userId, "❌ Format salah.");
                        continue;
                    }

                    if (get10RangeInput.has(userId)) {
                        get10RangeInput.delete(userId);
                        const prefix = text.trim();
                        let menuMsgId = pendingMessage[userId];
                        delete pendingMessage[userId];
                        if (/^\+?\d{3,15}[Xx*#]+$/.test(prefix)) {
                            processUserInput(userId, prefix, 10, usernameTg, firstName, menuMsgId);
                        } else await tgSend(chatId, "❌ Format salah.");
                        continue;
                    }

                    const isManualFormat = /^\+?\d{3,15}[Xx*#]+$/.test(text.trim());
                    if (manualRangeInput.has(userId) || (verifiedUsers.has(userId) && isManualFormat)) {
                        manualRangeInput.delete(userId);
                        const prefix = text.trim();
                        let menuMsgId = pendingMessage[userId];
                        delete pendingMessage[userId];
                        if (isManualFormat) {
                            processUserInput(userId, prefix, 1, usernameTg, firstName, menuMsgId);
                        } else await tgSend(chatId, "❌ Format salah.");
                        continue;
                    }

                    if (text.startsWith("/setdana")) {
                        waitingDanaInput.add(userId);
                        await tgSend(userId, "Kirim format: NoDana (enter) Nama");
                        continue;
                    }

                    if (text === "/start") {
                        if (await isUserInBothGroups(userId)) {
                            verifiedUsers.add(userId); saveUsers(userId);
                            const prof = getUserProfile(userId, firstName);
                            const fullName = usernameTg ? `${firstName} (@${usernameTg})` : firstName;
                            const msgProfile = `✅ <b>Verifikasi Berhasil</b>\nName: ${fullName}\nBalance: $${prof.balance.toFixed(6)}`;
                            const kb = { inline_keyboard: [[{ text: "📲 Get Number", callback_data: "getnum" }], [{ text: "💸 Withdraw", callback_data: "withdraw_menu" }]] };
                            await tgSend(userId, msgProfile, kb);
                        } else {
                            const kb = { inline_keyboard: [[{ text: "📌 Grup 1", url: GROUP_LINK_1 }], [{ text: "📌 Grup 2", url: GROUP_LINK_2 }], [{ text: "✅ Verifikasi", callback_data: "verify" }]] };
                            await tgSend(userId, `Halo ${mention}, Gabung grup dulu:`, kb);
                        }
                        continue;
                    }
                }

                if (upd.callback_query) {
                    const cq = upd.callback_query;
                    const userId = cq.from.id;
                    const dataCb = cq.data;
                    const chatId = cq.message.chat.id;
                    const menuMsgId = cq.message.message_id;
                    const firstName = cq.from.first_name || "User";
                    const usernameTg = cq.from.username;

                    if (dataCb === "verify") {
                        if (await isUserInBothGroups(userId)) {
                            verifiedUsers.add(userId); saveUsers(userId);
                            await tgEdit(chatId, menuMsgId, "✅ Verifikasi Sukses! Ketik /start");
                        } else { await tgSend(chatId, "❌ Belum gabung semua grup."); }
                        continue;
                    }
                    if (dataCb === "getnum") {
                        if (!verifiedUsers.has(userId)) continue;
                        const ranges = loadInlineRanges();
                        const kb = ranges.length > 0 ? generateInlineKeyboard(ranges) : { inline_keyboard: [[{ text: "✍️ Manual Range", callback_data: "manual_range" }]] };
                        await tgEdit(chatId, menuMsgId, "Pilih Range:", kb);
                        continue;
                    }
                    if (dataCb === "manual_range") {
                        manualRangeInput.add(userId);
                        await tgEdit(chatId, menuMsgId, "Kirim Range manual:");
                        pendingMessage[userId] = menuMsgId;
                        continue;
                    }
                    if (dataCb.startsWith("select_range:")) {
                        const prefix = dataCb.split(":")[1];
                        processUserInput(userId, prefix, 1, usernameTg, firstName, menuMsgId);
                        continue;
                    }
                    if (dataCb.startsWith("change_num:")) {
                        const parts = dataCb.split(":");
                        await tgDelete(chatId, menuMsgId);
                        processUserInput(userId, parts[2], parseInt(parts[1]), usernameTg, firstName);
                        continue;
                    }
                    if (dataCb === "withdraw_menu") {
                        const prof = getUserProfile(userId, firstName);
                        const kbWd = { inline_keyboard: [[{ text: "$1", callback_data: "wd_req:1.0" }, { text: "$2", callback_data: "wd_req:2.0" }], [{ text: "🔙 Back", callback_data: "verify" }]] };
                        await tgEdit(chatId, menuMsgId, `Saldo: $${prof.balance.toFixed(6)}`, kbWd);
                        continue;
                    }
                    if (dataCb.startsWith("wd_req:")) {
                        const amount = parseFloat(dataCb.split(":")[1]);
                        const prof = loadProfiles()[String(userId)];
                        if (prof && prof.balance >= amount) {
                            prof.balance -= amount; saveProfiles(loadProfiles());
                            await tgSend(ADMIN_ID, `User ${userId} WD $${amount}`, { inline_keyboard: [[{ text: "Approve", callback_data: `wd_act:apr:${userId}:${amount}` }, { text: "Cancel", callback_data: `wd_act:cncl:${userId}:${amount}` }]] });
                            await tgEdit(chatId, menuMsgId, "✅ WD Request sent.");
                        } else await tgSend(chatId, "❌ Saldo kurang.");
                        continue;
                    }
                    if (dataCb.startsWith("wd_act:") && userId === ADMIN_ID) {
                        const parts = dataCb.split(":");
                        const action = parts[1];
                        const targetId = parseInt(parts[2]);
                        const amount = parseFloat(parts[3]);
                        if (action === "apr") {
                            await tgEdit(chatId, menuMsgId, "✅ WD Approved.");
                            await tgSend(targetId, "✅ WD Sukses.");
                        } else {
                            const profiles = loadProfiles();
                            profiles[String(targetId)].balance += amount; saveProfiles(profiles);
                            await tgEdit(chatId, menuMsgId, "❌ WD Cancelled.");
                            await tgSend(targetId, "❌ WD Dibatalkan.");
                        }
                        continue;
                    }
                }
            }
        }
        await new Promise(r => setTimeout(r, 50));
    }
}

async function expiryMonitorTask() {
    setInterval(async () => {
        try {
            const waitList = loadWaitList();
            const now = Date.now() / 1000;
            const updatedList = [];
            for (const item of waitList) {
                if (now - item.timestamp > 1200) {
                    const msgId = await tgSend(item.user_id, `⚠️ Nomor ${item.number} expired.`);
                    if (msgId) setTimeout(() => tgDelete(item.user_id, msgId), 30000);
                } else updatedList.push(item);
            }
            saveWaitList(updatedList);
        } catch (e) { }
    }, 10000);
}

// ==============================================================================
// INITIALIZATION
// ==============================================================================

function initializeFiles() {
    [CACHE_FILE, INLINE_RANGE_FILE, AKSES_GET10_FILE, USER_FILE, WAIT_FILE].forEach(f => { if (!fs.existsSync(f)) saveJson(f, []); });
    if (!fs.existsSync(PROFILE_FILE)) saveJson(PROFILE_FILE, {});
}

async function main() {
    console.log("[INFO] Starting NodeJS Bot (Standby Page & Queue Mode)...");
    initializeFiles();
    
    // --- 1. START SHARED BROWSER ---
    try {
        await initSharedBrowser(STEX_EMAIL, STEX_PASSWORD);
        console.log("[MAIN] Shared Browser Ready.");

        // --- 2. PREPARE STANDBY PAGE ---
        mainStandbyPage = await getNewPage();
        await mainStandbyPage.goto(TARGET_URL, { waitUntil: 'domcontentloaded' });
        console.log("[MAIN] Standby Page Ready.");

    } catch (e) {
        console.error("[FATAL] Gagal Start Browser/Standby Page:", e);
        process.exit(1);
    }

    const smsProcess = fork('./sms.js', [], { silent: true });

    // CRON: Restart Browser & Re-init Standby Page
    cron.schedule('0 7 * * *', async () => {
        console.log("[CRON] Restarting Browser...");
        await restartBrowser(STEX_EMAIL, STEX_PASSWORD);
        mainStandbyPage = await getNewPage();
        await mainStandbyPage.goto(TARGET_URL);
    }, { scheduled: true, timezone: "Asia/Jakarta" });

    try {
        await Promise.all([ telegramLoop(), expiryMonitorTask() ]);
    } catch (e) { console.error("[FATAL ERROR]", e); } 
    finally { smsProcess.kill(); }
}

if (!fs.existsSync('sms.js')) fs.writeFileSync('sms.js', "console.log('SMS Service Mock'); setInterval(()=>{},10000);");

main();
