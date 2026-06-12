function addChapter() {
    const container = document.getElementById('chapters');
    const fieldsets = container.querySelectorAll('fieldset');
    const idx = fieldsets.length;

    const fs = document.createElement('fieldset');
    fs.dataset.idx = idx;
    fs.innerHTML = `
        <legend>챕터 ${idx + 1} <button type="button" class="outline secondary remove-ch" onclick="removeChapter(this)">&times;</button></legend>
        <label>제목
            <input type="text" name="chapter_title_${idx}" required>
        </label>
        <label>설명
            <textarea name="chapter_desc_${idx}" rows="2"></textarea>
        </label>
    `;
    container.appendChild(fs);
}

function removeChapter(btn) {
    const fs = btn.closest('fieldset');
    const container = document.getElementById('chapters');
    if (container.querySelectorAll('fieldset').length <= 1) {
        alert('최소 1개 챕터가 필요합니다.');
        return;
    }
    fs.remove();
    renumber();
}

function renumber() {
    const container = document.getElementById('chapters');
    container.querySelectorAll('fieldset').forEach((fs, i) => {
        fs.dataset.idx = i;
        fs.querySelector('legend').childNodes[0].textContent = `챕터 ${i + 1} `;
        fs.querySelector('input[type="text"]').name = `chapter_title_${i}`;
        fs.querySelector('textarea').name = `chapter_desc_${i}`;
    });
}
