from bs4 import BeautifulSoup


def extract_chq(chq: str) -> int:
    chq_length = len(chq)

    bytes_array = bytearray(chq_length // 2)
    xor_key = 157

    for i in range(0, chq_length, 2):
        bytes_array[i // 2] = int(chq[i:i + 2], 16)

    xor_bytes = bytearray(t ^ xor_key for t in bytes_array)
    decoded_xor = xor_bytes.decode('utf-8')

    js_code = (decoded_xor.split('try {eval("document.getElementById");} catch {return 0xC0FEBABE;}')[1].split('})')[0]
               .strip())

    html = js_code.split('rt["inner" + "HTM" + "L"] = ')[1].split('\n')[0]
    soup = BeautifulSoup(html, 'html.parser')

    div_elements = soup.find_all('div')
    codes = {}
    for div in div_elements:
        if 'id' in div.attrs and '_d_' in div.attrs:
            codes[div['id']] = div['_d_']

    va = None
    vb = None
    for k, v in codes.items():
        if k in js_code.split('\n')[5]:
            va = v
        if k in js_code.split('\n')[6]:
            vb = v

    code_to_execute = js_code.split('return ')[1].split(';')[0].replace('va', va).replace('vb', vb)

    return eval(code_to_execute)
