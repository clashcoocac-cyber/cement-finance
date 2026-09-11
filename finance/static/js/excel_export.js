/**
 * Export button: fetches the .xlsx, triggers the download, then restores
 * the button. Shows ⏳ while loading and ❌ on error.
 */
async function exportWait(el) {
    if (el.dataset.busy) return false;
    el.dataset.busy = '1';

    const orig = el.textContent;
    el.textContent = '⏳ Yuklanmoqda...';
    el.style.opacity = '0.7';
    el.style.pointerEvents = 'none';

    try {
        const resp = await fetch(el.href);
        if (!resp.ok) throw new Error('HTTP ' + resp.status);

        const blob = await resp.blob();
        const cd = resp.headers.get('Content-Disposition') || '';
        const m = cd.match(/filename="([^"]+)"/);
        const name = m ? m[1] : 'hisobot.xlsx';

        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = name;
        document.body.appendChild(a);
        a.click();
        a.remove();
        URL.revokeObjectURL(url);

        el.textContent = '✅ Yuklandi';
    } catch (e) {
        console.error('Excel eksport xatosi:', e);
        el.textContent = '❌ Xatolik';
        alert("Hisobotni yuklashda xatolik yuz berdi. Qayta urinib ko'ring.");
    }

    setTimeout(() => {
        el.textContent = orig;
        el.style.opacity = '';
        el.style.pointerEvents = '';
        delete el.dataset.busy;
    }, 2000);

    return false;
}
