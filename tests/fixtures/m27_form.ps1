# M27 test form (F1): Pseudo's own fake window for measuring actions. Every value here is FAKE.
# Each control's effect can be read back through UI Automation (a value, a tick, a selection, the status line).
#   -HandleFile  where to write "form=<handle> cover=<handle>" once the windows exist
#   -StateFile   polled every 300 ms: "cover" shows the cover window over "Mark as done" (the T2 hit-test case)
#   -Minutes     the form closes itself after this long, whatever happens to the runner
# Committed before any measurement (M27).
param([string]$HandleFile, [string]$StateFile = "", [int]$Minutes = 20)

Add-Type -AssemblyName System.Windows.Forms, System.Drawing
$font = New-Object System.Drawing.Font("Segoe UI", 11)

# A hidden launch hides the FIRST window this process shows; a throwaway window takes that hit (as in M18).
$dummy = New-Object System.Windows.Forms.Form
$dummy.ShowInTaskbar = $false; $dummy.Size = "1,1"; $dummy.Show(); $dummy.Close()

$form = New-Object System.Windows.Forms.Form
$form.Text = "Pseudo M27 test form (fake)"; $form.Font = $font
$form.StartPosition = "Manual"; $form.Location = "80,80"; $form.Size = "560,640"
$script:y = 12

function Add-Control($control, [string]$name, [int]$height = 30) {
    $control.AccessibleName = $name  # the Name UI Automation reports
    $control.Location = "12,$script:y"; $control.Width = 500; $control.Height = $height
    $form.Controls.Add($control); $script:y += $height + 8
    return $control
}

$status = Add-Control (New-Object System.Windows.Forms.Label) "Status"
$status.Text = "Status: waiting (fake)"
$done = Add-Control (New-Object System.Windows.Forms.Button) "Mark as done"
$done.Text = "Mark as done"
$done.Add_Click({ $status.Text = "Status: done (fake)"; $done.Text = "Marked (fake)"; $done.AccessibleName = "Marked (fake)" })
$subject = Add-Control (New-Object System.Windows.Forms.TextBox) "Subject"
$notes = Add-Control (New-Object System.Windows.Forms.TextBox) "Notes" 60
$notes.Multiline = $true
$password = Add-Control (New-Object System.Windows.Forms.TextBox) "Portal password"
$password.UseSystemPasswordChar = $true; $password.Text = "fake-pass-123"
$remind = Add-Control (New-Object System.Windows.Forms.CheckBox) "Send me reminders"
$remind.Text = "Send me reminders"
$low = Add-Control (New-Object System.Windows.Forms.RadioButton) "Priority low"
$low.Text = "Priority low"; $low.Checked = $true
$high = Add-Control (New-Object System.Windows.Forms.RadioButton) "Priority high"
$high.Text = "Priority high"
$room = Add-Control (New-Object System.Windows.Forms.ComboBox) "Room"
$room.DropDownStyle = "DropDownList"; [void]$room.Items.AddRange(@("Room 101", "Room 204", "Room 305")); $room.SelectedIndex = 0
$course = Add-Control (New-Object System.Windows.Forms.ListBox) "Course" 70
[void]$course.Items.AddRange(@("CS101", "MA102", "PH103"))
$archive = Add-Control (New-Object System.Windows.Forms.Button) "Archive (disabled)"
$archive.Text = "Archive (disabled)"; $archive.Enabled = $false
$sentinel = Add-Control (New-Object System.Windows.Forms.TextBox) "Sentinel (never changes)"
$sentinel.Text = "SENTINEL-41"

# The cover (R11): a small always-on-top window that can sit exactly over "Mark as done".
$cover = New-Object System.Windows.Forms.Form
$cover.Text = "Pseudo M27 cover (fake)"; $cover.TopMost = $true; $cover.ShowInTaskbar = $false
$cover.FormBorderStyle = "None"; $cover.BackColor = "Orange"; $cover.StartPosition = "Manual"

$poll = New-Object System.Windows.Forms.Timer
$poll.Interval = 300
$poll.Add_Tick({
    if (-not $StateFile -or -not (Test-Path $StateFile)) { return }
    $want = (Get-Content $StateFile -Raw).Trim()
    if ($want -eq "cover" -and -not $cover.Visible) {
        $spot = $done.PointToScreen([System.Drawing.Point]::Empty)
        $cover.Location = $spot; $cover.Size = $done.Size; $cover.Show()
    } elseif ($want -ne "cover" -and $cover.Visible) { $cover.Hide() }
})
$quit = New-Object System.Windows.Forms.Timer
$quit.Interval = $Minutes * 60 * 1000
$quit.Add_Tick({ $quit.Stop(); $form.Close() })

$form.Add_FormClosed({ $cover.Close(); [System.Windows.Forms.Application]::ExitThread() })
$form.Show()
$poll.Start(); $quit.Start()
"form=$($form.Handle.ToInt64())`ncover=$($cover.Handle.ToInt64())" | Set-Content -Encoding ascii $HandleFile
[System.Windows.Forms.Application]::Run()
