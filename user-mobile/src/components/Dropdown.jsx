import { forwardRef, useEffect, useImperativeHandle, useRef, useState } from 'react';
import { ChevronDown } from 'lucide-react';
import './Dropdown.css';

// Custom-styled replacement for a native <select>. Native selects can't be
// reliably skinned across real devices — Android/iOS render their own
// OS-level picker for the open list that mostly ignores page CSS — so this
// builds the open/closed states ourselves to match the app everywhere a
// dropdown appears, instead of inheriting whatever the OS looks like.
const Dropdown = forwardRef(function Dropdown(
  { value, onChange, options, placeholder = '', ariaLabel, className = '' },
  ref,
) {
  const [open, setOpen] = useState(false);
  const containerRef = useRef(null);
  const triggerRef = useRef(null);

  // Lets a parent do `someRef.current?.focus()` on this the same way it
  // would on a native <select> (see ManualReport.jsx's "Manual only" skip
  // link) — focuses the trigger and opens the list, since a plain focus()
  // with nothing visibly open wouldn't tell the farmer what to do next.
  useImperativeHandle(ref, () => ({
    focus: () => {
      triggerRef.current?.focus();
      setOpen(true);
    },
  }));

  useEffect(() => {
    if (!open) return undefined;

    const handlePointer = (e) => {
      if (containerRef.current && !containerRef.current.contains(e.target)) setOpen(false);
    };
    const handleKey = (e) => {
      if (e.key === 'Escape') setOpen(false);
    };

    document.addEventListener('mousedown', handlePointer);
    document.addEventListener('keydown', handleKey);
    return () => {
      document.removeEventListener('mousedown', handlePointer);
      document.removeEventListener('keydown', handleKey);
    };
  }, [open]);

  const selected = options.find((opt) => opt.value === value);

  return (
    <div className={`app-dropdown ${className}`} ref={containerRef}>
      <button
        type="button"
        ref={triggerRef}
        className={`app-dropdown-trigger${!selected ? ' is-placeholder' : ''}`}
        onClick={() => setOpen((prev) => !prev)}
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-label={ariaLabel}
      >
        <span>{selected ? selected.label : placeholder}</span>
        <ChevronDown size={16} className={`app-dropdown-chevron${open ? ' is-open' : ''}`} />
      </button>

      {open && (
        <ul className="app-dropdown-list" role="listbox">
          {options.map((opt) => (
            <li key={opt.value} role="option" aria-selected={opt.value === value}>
              <button
                type="button"
                className={`app-dropdown-option${opt.value === value ? ' is-selected' : ''}`}
                onClick={() => {
                  onChange(opt.value);
                  setOpen(false);
                }}
              >
                {opt.label}
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
});

export default Dropdown;
