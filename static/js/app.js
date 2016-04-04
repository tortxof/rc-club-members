$("#expire").dateDropper({
  format: "Y-m-d",
  maxYear: 2030,
  animate_current: false
});

$(".clksel").click(function() {
  $(this).select();
});
