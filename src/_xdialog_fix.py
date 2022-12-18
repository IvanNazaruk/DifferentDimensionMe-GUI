import ctypes
import platform

import xdialog

if platform.system() == 'Windows':
    from xdialog.windows_dialogs import comdlg32, BUFFER_SIZE, split_null_list
    from xdialog.windows_structs import tagOFNW


    def open_file(title, filetypes, multiple=False):
        file = ctypes.create_unicode_buffer(BUFFER_SIZE)
        pfile = ctypes.cast(file, ctypes.c_wchar_p)

        # Default options
        opts = tagOFNW(
            lStructSize=ctypes.sizeof(tagOFNW),

            lpstrFile=pfile,
            nMaxFile=BUFFER_SIZE,

            lpstrTitle=title,
            Flags=0x00081808 + (0x200 if multiple else 0)
        )

        # Filetypes
        if filetypes:
            out = []
            for s, t in filetypes:
                out.append(f'{s} ({t})\0{";".join(t.split())}\0')

            string = ''.join(out) + '\0'
            buffer = ctypes.create_unicode_buffer(string, len(string) + 2)
            opts.lpstrFilter = ctypes.addressof(buffer)  # Extra NULL byte just in case
            opts.lpstrDefExt = ctypes.addressof(buffer)  # Extra NULL byte just in case

        # Call file dialog
        ok = comdlg32.GetOpenFileNameW(ctypes.byref(opts))

        # Return data
        if multiple:
            if ok:
                # Windows splits the parent folder, followed by files, by null characters.
                gen = split_null_list(pfile)
                parent = next(gen)
                return [parent + "\\" + f for f in gen] or [parent]
            else:
                return []
        else:
            if ok:
                return file.value
            else:
                return ''


    xdialog.dialogs.open_file = open_file
